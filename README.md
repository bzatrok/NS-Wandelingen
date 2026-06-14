# NS Wandelingen Map

An interactive OpenStreetMap showing all 47 NS walking routes
(NS-wandelingen) across the Netherlands — with train stations, railway
lines, GPX downloads and fuzzy search.

**Live at <https://ns-wandelingen.zatrok.com/>**

## What it shows

- **47 NS walking routes** — GPX tracks downloaded from Wandelnet, rendered as
  colored polylines with a subtle glow, start (green) and end (red) markers.
- **397 NL train stations** — yellow dots for stations used as the start/end
  of a hike, grey dots for the rest. Major stations are labeled.
- **NL railway network** — grey dashed lines in the background (~14.6k ways
  from OpenStreetMap via Overpass).
- **Fuzzy search** (Fuse.js) over route names, locations, provinces and
  major stations. Top-left Google-Maps-style panel.
- **Rich popup cards** with the NS hero photo, distance, route endpoints,
  description, a "Bekijk details" button and a one-click GPX download.
- **Detail modal** (per route) with hero image, stat badges, a non-interactive
  route map, an elevation profile and a 7-day weather forecast (both from the
  keyless [Open-Meteo](https://open-meteo.com/) API), plus ns.nl / GPX /
  shareable-link actions. Opening `?hike=<slug>` deep-links straight into it.
- **Legend**, **geolocation button**, **mobile-responsive**.

## Architecture

Pure static site — no backend:

```
index.html        Leaflet + Fuse.js + all UI
hikes.json        47 NS routes with metadata (source: "ns")
klompenpaden.json Utrecht klompenpaden — circular walks (source: "klompenpad")
stations.json     397 NL stations (code, name, lat/lng, type)
railways.geojson  NL main+branch rail lines
gpx/*.gpx         downloaded GPX tracks (ns + klompenpad-*)
```

Both NS routes and klompenpaden share one map. A category filter (bottom-left)
toggles each set independently. Klompenpaden are circular — drawn in a single
green colour with one start/finish marker; NS routes stay multi-coloured with
green start / red end markers.

All route/station data is baked at build time by `fetch.py`. The only
runtime API calls are to Open-Meteo (elevation + weather), made lazily when
a route's detail modal is opened and cached in `localStorage`.

## Data pipeline (`fetch.py`)

`fetch.py` is idempotent and pulls from these sources:

1. **NS route listing** — scraped from `https://www.ns.nl/dagje-uit/wandelen`
   (parses the `app-dagjeuit` component's `appData` JSON).
2. **GPX tracks** — each route's NS detail page links to Wandelnet; the
   Wandelnet page exposes `https://wandelnet.api.routemaker.nl/content/gpx/wandelnet/{id}.gpx`.
3. **NS stations** — NS Gateway API (`/reisinformatie-api/api/v2/stations`).
   Requires `NS_API_KEY`. Filters to NL.
4. **NL railways** — OpenStreetMap via Overpass API. Filters to
   `railway=rail` with `usage=main|branch`.
5. **Klompenpaden** — the Province of Utrecht ArcGIS REST service
   (`gis.provincie-utrecht.nl/.../Recreatie/s01_4_toerisme_recreatie/MapServer`),
   queried as GeoJSON. The line features are grouped into routes, written to
   `gpx/klompenpad-*.gpx`, and summarised in `klompenpaden.json`. Covers the
   Utrecht klompenpaden only; Gelderland lives in a separate source (TODO).
   Layer/field names are detected defensively — if the service schema changes,
   adjust `KP_SERVICE` and the field lists in `fetch_klompenpaden()`.

### Run the pipeline

```bash
# One-time: put NS_API_KEY=… in .env (gitignored) or export it.
export NS_API_KEY=your_subscription_key

python3 fetch.py
```

Each output file (`hikes.json`, `klompenpaden.json`, `stations.json`,
`railways.geojson`, `gpx/*.gpx`) is skipped if it already exists. Delete the
file to force a refresh.

Get a free NS API key at <https://apiportal.ns.nl>.

## Local development

The site is plain static files. `fetch()` won't work over `file://`, so
serve it:

```bash
python3 -m http.server 8765
# → http://localhost:8765
```

Or use Docker:

```bash
docker compose up -d --build
# → http://localhost:8765
```

The compose file runs a tiny `nginx:alpine` image with the static assets
baked in.

## Deployment

Hosted on **Cloudflare Pages**, deployed automatically on every push to
`master` via GitHub integration.

- Production branch: `master`
- Build command: *(none)*
- Output directory: `/`

## Privacy

- No cookies.
- No tracking pixels except **Simple Analytics** (privacy-first, honors
  Do Not Track).
- GPX files and station/railway data are served statically — no calls to
  NS or OSM from the browser at runtime.

## Stack

- [Leaflet](https://leafletjs.com/) 1.9 for the map
- [CARTO Positron](https://carto.com/basemaps/) tiles (minimal basemap)
- [Fuse.js](https://fusejs.io/) 7 for fuzzy search
- [Simple Analytics](https://www.simpleanalytics.com/) for privacy-first stats
- Python 3 (stdlib only) for the data pipeline

## Attributions

- Map tiles: © OpenStreetMap contributors, © CARTO
- Railway geometry: © OpenStreetMap contributors (Overpass API)
- Station data: © NS (via apiportal.ns.nl)
- Route data and GPX: © NS / Wandelnet

## License

Code: MIT. Data: respective sources above.
