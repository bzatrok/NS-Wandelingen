#!/usr/bin/env python3
"""Download all NS wandeling GPX files and build a consolidated JSON."""
import html, json, os, re, time, urllib.parse, urllib.request, pathlib, sys

BASE = pathlib.Path(__file__).parent
GPX_DIR = BASE / "gpx"
GPX_DIR.mkdir(exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (ns-wandelingen-map)"}

def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def load_listing() -> list[dict]:
    h = get("https://www.ns.nl/dagje-uit/wandelen").decode("utf-8", "replace")
    m = re.search(r'appData="([^"]*)"', h)
    if not m:
        raise RuntimeError("appData not found")
    return json.loads(html.unescape(m.group(1)))["results"]

def wandelnet_id_from_detail(ns_url: str) -> tuple[str | None, str | None]:
    h = get("https://www.ns.nl" + ns_url).decode("utf-8", "replace")
    m = re.search(r'https://www\.wandelnet\.nl/wandelroute/(\d+)/([^"\'?#]+)', h)
    if not m:
        return None, None
    return m.group(1), m.group(2)

def fetch_railways():
    out = BASE / "railways.geojson"
    if out.exists():
        print(f"railways.geojson exists ({out.stat().st_size/1024:.0f} KB), skipping")
        return
    print("fetching NL railways from Overpass…")
    q = """
[out:json][timeout:180];
area["ISO3166-1"="NL"][admin_level=2]->.nl;
way(area.nl)["railway"="rail"]["usage"~"^(main|branch)$"];
out geom;
"""
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
    feats = []
    for el in resp.get("elements", []):
        if el.get("type") != "way" or not el.get("geometry"):
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {},
        })
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
    print(f"  saved {len(feats)} ways ({out.stat().st_size/1024:.0f} KB)")


def fetch_stations():
    out = BASE / "stations.json"
    if out.exists():
        print(f"stations.json exists, skipping")
        return
    key = os.environ.get("NS_API_KEY")
    if not key:
        # Also try .env in project dir
        env_path = BASE / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("NS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        print("NS_API_KEY not set, skipping stations")
        return
    print("fetching NS stations…")
    req = urllib.request.Request(
        "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2/stations",
        headers={"Ocp-Apim-Subscription-Key": key, **UA},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    stations = [
        {"code": s["code"], "name": s["namen"]["lang"], "lat": s["lat"], "lng": s["lng"], "type": s.get("stationType", "")}
        for s in d["payload"]
        if s.get("land") == "NL" and s.get("lat") and s.get("lng")
    ]
    stations.sort(key=lambda x: x["name"])
    out.write_text(json.dumps(stations, ensure_ascii=False, separators=(",", ":")))
    print(f"  saved {len(stations)} NL stations")


# --- Klompenpaden (Provincie Utrecht GIS) ---------------------------------
# Klompenpaden are circular ("rondwandelingen") unpaved farmland walks in the
# Utrecht/Gelderland landscape. The Province of Utrecht publishes them through
# an ArcGIS REST service that can emit GeoJSON directly, so no HTML scraping is
# needed. We pull the line geometry, group features into routes and write one
# GPX track per route plus a klompenpaden.json that mirrors the hikes.json shape
# (with source="klompenpad", circular=true). Only the Utrecht paden are covered
# here; the Gelderland ones live in a separate source and can be added later.
KP_SERVICE = "https://gis.provincie-utrecht.nl/server/rest/services/Recreatie/s01_4_toerisme_recreatie/MapServer"

def _slugify(name: str) -> str:
    s = name.lower()
    for a, b in (("é","e"),("è","e"),("ë","e"),("ê","e"),("ï","i"),("í","i"),
                 ("ö","o"),("ó","o"),("ü","u"),("ú","u"),("ä","a"),("á","a"),("ç","c")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "klompenpad"

def _prop(props: dict, *cands):
    """Case-insensitive lookup of the first present, non-empty property."""
    lower = {str(k).lower(): v for k, v in (props or {}).items()}
    for c in cands:
        v = lower.get(c.lower())
        if v not in (None, "", " "):
            return v
    return None

def _arcgis_geojson(layer_url: str) -> list[dict]:
    """Fetch all features of an ArcGIS layer as GeoJSON (handles paging)."""
    feats, offset = [], 0
    while True:
        params = urllib.parse.urlencode({
            "where": "1=1", "outFields": "*", "outSR": "4326",
            "returnGeometry": "true", "f": "geojson",
            "resultOffset": offset, "resultRecordCount": 1000,
        })
        gj = json.loads(get(f"{layer_url}/query?{params}"))
        batch = gj.get("features", [])
        feats.extend(batch)
        if not batch or not gj.get("exceededTransferLimit"):
            break
        offset += len(batch)
    return feats

def _coords_from_geom(geom: dict) -> list[list[float]]:
    if not geom:
        return []
    t, c = geom.get("type"), geom.get("coordinates") or []
    if t == "LineString":
        return c
    if t == "MultiLineString":
        out = []
        for part in c:
            out.extend(part)
        return out
    return []

def _write_gpx(path: pathlib.Path, name: str, coords: list[list[float]]):
    pts = "".join(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"></trkpt>' for lon, lat in coords)
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="ns-wandelingen-map" xmlns="http://www.topografix.com/GPX/1/1">'
        f'<trk><name>{html.escape(name)}</name><trkseg>{pts}</trkseg></trk></gpx>',
        encoding="utf-8",
    )

def fetch_klompenpaden():
    out = BASE / "klompenpaden.json"
    if out.exists():
        print("klompenpaden.json exists, skipping")
        return
    print("fetching Klompenpaden from Provincie Utrecht GIS…")
    try:
        meta = json.loads(get(KP_SERVICE + "?f=json"))
    except Exception as e:
        print(f"  could not reach GIS service: {e}")
        return
    # Pick the line layer(s) whose name mentions "klompenpad". The root service
    # JSON usually omits geometryType, so confirm it per layer.
    line_layers = []
    for l in meta.get("layers", []):
        if "klompenpad" not in str(l.get("name", "")).lower():
            continue
        try:
            info = json.loads(get(f"{KP_SERVICE}/{l['id']}?f=json"))
        except Exception:
            continue
        if info.get("geometryType") == "esriGeometryPolyline":
            line_layers.append(l)
    if not line_layers:
        print("  no klompenpaden line layer found — check service/layer names in KP_SERVICE")
        return

    routes: dict[str, dict] = {}
    for l in line_layers:
        try:
            feats = _arcgis_geojson(f"{KP_SERVICE}/{l['id']}")
        except Exception as e:
            print(f"  layer {l['id']} query failed: {e}")
            continue
        for f in feats:
            coords = _coords_from_geom(f.get("geometry"))
            if len(coords) < 2:
                continue
            props = f.get("properties", {}) or {}
            name = _prop(props, "NAAM", "naam", "ROUTENAAM", "NAAM_ROUTE", "NAME",
                         "TITEL", "THEMA", "OMSCHRIJVING") or f"Klompenpad {len(routes) + 1}"
            slug = _slugify(str(name))
            r = routes.setdefault(slug, {"name": str(name), "coords": [], "props": props})
            r["coords"].extend(coords)

    if not routes:
        print("  no klompenpaden line features returned (schema may differ)")
        return

    items = []
    for slug, r in sorted(routes.items()):
        gpx_name = f"klompenpad-{slug}.gpx"
        _write_gpx(GPX_DIR / gpx_name, r["name"], r["coords"])
        length = _prop(r["props"], "LENGTE", "LENGTH", "AFSTAND", "Shape__Length", "SHAPE_Length")
        try:
            km = round(float(length) / 1000, 1) if length else None
        except (TypeError, ValueError):
            km = None
        items.append({
            "id": "kp-" + slug,
            "slug": "klompenpad-" + slug,
            "title": r["name"],
            "shortTitle": r["name"],
            "description": _prop(r["props"], "OMSCHRIJVING", "BESCHRIJVING", "TEKST", "INFO") or "",
            "location": _prop(r["props"], "PLAATS", "WOONPLAATS", "STARTPUNT", "GEMEENTE") or "",
            "distanceKm": km,
            "distanceText": (f"{km:.1f} km".replace(".", ",")) if km else None,
            "provinces": ["utrecht"],
            "types": [],
            "suitableFor": [],
            "pavedPercentage": None,
            "image": None,
            "source": "klompenpad",
            "circular": True,
            "infoUrl": _prop(r["props"], "URL", "WEBSITE", "LINK") or "https://www.klompenpaden.nl",
            "gpxFile": f"gpx/{gpx_name}",
        })
    out.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    print(f"  saved {len(items)} klompenpaden + GPX tracks")


def main():
    fetch_railways()
    fetch_stations()
    fetch_klompenpaden()
    results = load_listing()
    print(f"Found {len(results)} routes on NS listing")
    hikes = []
    for i, r in enumerate(results, 1):
        short = r["korteTitel"]
        ns_url = r["url"]
        print(f"[{i}/{len(results)}] {short}", flush=True)
        try:
            wid, wslug = wandelnet_id_from_detail(ns_url)
        except Exception as e:
            print(f"  detail error: {e}")
            wid, wslug = None, None
        gpx_file = None
        gpx_url = None
        if wid:
            gpx_url = f"https://wandelnet.api.routemaker.nl/content/gpx/wandelnet/{wid}.gpx"
            out = GPX_DIR / f"{r['naam']}.gpx"
            if not out.exists():
                try:
                    data = get(gpx_url)
                    if data[:5] != b"<?xml" and b"<gpx" not in data[:200]:
                        print(f"  not a gpx response ({len(data)} bytes)")
                    else:
                        out.write_bytes(data)
                        print(f"  saved {out.name} ({len(data)} bytes)")
                except Exception as e:
                    print(f"  gpx download error: {e}")
            gpx_file = out.name if out.exists() else None
        else:
            print("  no wandelnet link on detail page")
        hikes.append({
            "id": r["id"],
            "source": "ns",
            "slug": r["naam"],
            "title": r["titel"],
            "shortTitle": short,
            "description": r["beschrijving"],
            "location": r["locatieTekst"],
            "distanceKm": r["afstanden"][0] if r["afstanden"] else None,
            "distanceText": r["afstandTekstvorm"],
            "provinces": r["provincies"],
            "types": r["soort"],
            "suitableFor": r["geschiktVoor"],
            "pavedPercentage": r["percentageVerhard"],
            "image": (r.get("hero") or {}).get("tegel", {}).get("url"),
            "nsUrl": "https://www.ns.nl" + ns_url,
            "wandelnetId": wid,
            "wandelnetUrl": f"https://www.wandelnet.nl/wandelroute/{wid}/{wslug}" if wid else None,
            "gpxUrl": gpx_url,
            "gpxFile": f"gpx/{gpx_file}" if gpx_file else None,
        })
        time.sleep(0.3)
    (BASE / "hikes.json").write_text(json.dumps(hikes, indent=2, ensure_ascii=False))
    ok = sum(1 for h in hikes if h["gpxFile"])
    print(f"\nDone. {ok}/{len(hikes)} GPX files saved. hikes.json written.")

if __name__ == "__main__":
    main()
