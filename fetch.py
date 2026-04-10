#!/usr/bin/env python3
"""Download all NS wandeling GPX files and build a consolidated JSON."""
import html, json, re, time, urllib.request, pathlib, sys

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

def main():
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
