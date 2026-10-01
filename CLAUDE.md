# NS Wandelingen Kaart

Static site: Leaflet map of all NS walking routes, live at https://ns-wandelingen.zatrok.com/. See README.md for what it shows and the data sources.

## Layout
- `index.html` — the whole map app (HTML, CSS, JS inline).
- `fetch.py` — data pipeline → `hikes.json`, `stations.json`, `railways.geojson`, `gpx/`.
- `build_pages.py` — generates `wandeling/` (per-route + overview pages) and `sitemap.xml`. Generated output is committed.
- `assets/pages.css` — styles for the generated pages only.

## Commands
- Serve locally: `python3 -m http.server 8765`, or `docker compose up -d --build` (port 8765).
- Rebuild SEO pages after any change to `hikes.json`/`gpx/` or to `build_pages.py`: `python3 build_pages.py`.
- Deploy: push to `master`; Cloudflare Pages publishes the repo root (no build command).

## Checks
No automated checks or tests. Design principles are unenforced here.
