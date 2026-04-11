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


def main():
    fetch_railways()
    fetch_stations()
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
