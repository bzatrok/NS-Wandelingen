#!/usr/bin/env python3
"""Generate one crawlable static page per route, an overview page and sitemap.xml.

Reads hikes.json and gpx/*.gpx; writes wandeling/<slug>/index.html,
wandeling/index.html and sitemap.xml. Run after fetch.py and before deploying:
the site has no build step on Cloudflare Pages, so the output is committed.
"""
import html, json, math, pathlib, re, xml.etree.ElementTree as ET

BASE = pathlib.Path(__file__).parent
SITE = "https://ns-wandelingen.zatrok.com"
OUT_DIR = BASE / "wandeling"

# Same labels as the map's detail modal (index.html TYPE_LABELS / PROVINCE_LABELS).
TYPE_LABELS = {
    "boerenland": "Boerenland", "bos": "Bos", "duinenenstrand": "Duinen & strand",
    "heideenzand": "Heide & zand", "landgoederen": "Landgoederen",
    "stadenomgeving": "Stad & omgeving", "waterlandenrivieren": "Water & rivieren",
}
PROVINCE_LABELS = {
    "drenthe": "Drenthe", "friesland": "Friesland", "gelderland": "Gelderland",
    "limburg": "Limburg", "noordbrabant": "Noord-Brabant", "noordholland": "Noord-Holland",
    "overijssel": "Overijssel", "utrecht": "Utrecht", "zeeland": "Zeeland", "zuidholland": "Zuid-Holland",
}

e = html.escape


def name(h: dict) -> str:
    """Route name without the 'NS-wandeling' prefix or trailing dot some NS titles carry."""
    return re.sub(r"^NS-wandeling\s+", "", h["shortTitle"]).rstrip(".")


def route_url(h: dict) -> str:
    return f"/wandeling/{h['slug']}/"


def clean_location(h: dict) -> str:
    """'Van station Almelo naar station Borne' -> 'station Almelo → station Borne'."""
    loc = (h.get("location") or "").rstrip(".")
    return re.sub(r"\s+naar\s+", " → ", re.sub(r"^Van\s+", "", loc))


def meta_description(h: dict, limit: int = 155) -> str:
    text = f"{(h.get('location') or '').rstrip('.')}. {h.get('description') or ''}".strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def read_track(gpx_file: str) -> list[tuple[float, float]]:
    root = ET.parse(BASE / gpx_file).getroot()
    return [(float(p.get("lat")), float(p.get("lon"))) for p in root.iter() if p.tag.endswith("trkpt")]


def route_svg(points: list[tuple[float, float]], width: int = 640, height: int = 400, pad: int = 24) -> str:
    """Inline SVG of the track: equirectangular projection scaled by cos(latitude)."""
    if len(points) < 2:
        return ""
    step = max(1, len(points) // 400)  # ~400 points is plenty at this size
    pts = points[::step] + [points[-1]]
    lat0 = sum(p[0] for p in pts) / len(pts)
    kx = math.cos(math.radians(lat0))
    xs = [lon * kx for _, lon in pts]
    ys = [-lat for lat, _ in pts]
    w = (max(xs) - min(xs)) or 1e-9
    h = (max(ys) - min(ys)) or 1e-9
    scale = min((width - 2 * pad) / w, (height - 2 * pad) / h)
    ox = (width - w * scale) / 2
    oy = (height - h * scale) / 2
    coords = [((x - min(xs)) * scale + ox, (y - min(ys)) * scale + oy) for x, y in zip(xs, ys)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    (sx, sy), (ex, ey) = coords[0], coords[-1]
    return (
        f'<svg class="route-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Verloop van de route">'
        f'<polyline points="{path}" fill="none" stroke="#003082" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="8" fill="#dc2626" stroke="#fff" stroke-width="3"/>'
        f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="8" fill="#16a34a" stroke="#fff" stroke-width="3"/>'
        "</svg>"
    )


def page(title: str, description: str, canonical: str, body: str, og_image: str, json_ld: list[dict]) -> str:
    ld = json.dumps({"@context": "https://schema.org", "@graph": json_ld}, ensure_ascii=False, indent=1)
    return f"""<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <meta name="theme-color" content="#003082">
  <link rel="canonical" href="{SITE}{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="NS Wandelingen Kaart">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:url" content="{SITE}{canonical}">
  <meta property="og:locale" content="nl_NL">
  <meta property="og:image" content="{e(og_image)}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/svg+xml"
    href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23003082'/%3E%3Ctext x='32' y='44' font-family='system-ui,-apple-system,sans-serif' font-size='34' font-weight='800' text-anchor='middle' fill='%23ffc917'%3ENS%3C/text%3E%3C/svg%3E">
  <link rel="stylesheet" href="/assets/pages.css">
  <script type="application/ld+json">
{ld}
  </script>
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/">NS Wandelingen Kaart</a>
    <nav><a href="/wandeling/">Alle wandelingen</a><a class="nav-map" href="/">Kaart</a></nav>
  </header>
  <main>
{body}
  </main>
  <footer class="site-footer">
    Routes en GPX: © NS / Wandelnet · Kaartdata: © OpenStreetMap-bijdragers ·
    <a href="/">Bekijk alle routes op de kaart</a>
  </footer>
  <script data-collect-dnt="true" async src="https://scripts.simpleanalyticscdn.com/latest.js"></script>
</body>
</html>
"""


def card(h: dict) -> str:
    img = f'<img src="{e(h["image"])}" alt="" loading="lazy" width="400" height="200">' if h.get("image") else ""
    return (
        f'<a class="card" href="{route_url(h)}">{img}<span class="card-body">'
        f'<span class="card-title">{e(name(h))}</span>'
        f'<span class="badge">{e(h["distanceText"])}</span> '
        f'<span class="card-loc">{e(clean_location(h))}</span></span></a>'
    )


def breadcrumb(items: list[tuple[str, str]]) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": SITE + url}
            for i, (name, url) in enumerate(items, 1)
        ],
    }


def route_page(h: dict, hikes: list[dict]) -> str:
    provinces = [PROVINCE_LABELS.get(p, p) for p in h.get("provinces", [])]
    badges = [h["distanceText"]]
    if h.get("pavedPercentage") is not None:
        badges.append(f"{h['pavedPercentage']}% verhard")
    badges += [TYPE_LABELS.get(t, t) for t in h.get("types", [])] + provinces
    if "honden" in h.get("suitableFor", []):
        badges.append("Honden welkom")

    related = [o for o in hikes if o["id"] != h["id"] and set(o.get("provinces", [])) & set(h.get("provinces", []))][:6]
    related_html = ""
    if related:
        related_html = (
            f'<section><h2>Meer NS-wandelingen in {e(" en ".join(provinces))}</h2>'
            f'<div class="grid">{"".join(card(o) for o in related)}</div></section>'
        )

    title = f"NS-wandeling {name(h)} ({h['distanceText']}) | Route, kaart en GPX"
    description = meta_description(h)
    body = f"""    <nav class="crumbs"><a href="/">Kaart</a> › <a href="/wandeling/">Wandelingen</a> › {e(name(h))}</nav>
    <article>
      <h1>NS-wandeling {e(name(h))}</h1>
      <p class="lead">{e(clean_location(h))}</p>
      {f'<img class="hero" src="{e(h["image"])}" alt="{e(name(h))}" width="1200" height="600">' if h.get("image") else ""}
      <ul class="badges">{"".join(f"<li>{e(b)}</li>" for b in badges)}</ul>
      <p>{e(h.get('description') or '')}</p>
      <div class="actions">
        <a class="btn btn-primary" href="/?hike={e(h['slug'])}">Bekijk op de kaart</a>
        <a class="btn" href="/{e(h['gpxFile'])}" download="{e(h['slug'])}.gpx">Download GPX</a>
        <a class="btn" href="{e(h['nsUrl'])}" rel="noopener">Routebeschrijving op ns.nl</a>
      </div>
      <h2>Het verloop van de route</h2>
      <p class="muted">Groen is de start, rood het einde.</p>
      {route_svg(read_track(h['gpxFile']))}
    </article>
    {related_html}"""
    json_ld = [
        {
            "@type": "TouristTrip",
            "@id": f"{SITE}{route_url(h)}#route",
            "name": f"NS-wandeling {name(h)}",
            "description": h.get("description"),
            "url": SITE + route_url(h),
            "image": h.get("image"),
            "touristType": "Wandelaars",
            "inLanguage": "nl-NL",
        },
        breadcrumb([("Kaart", "/"), ("Wandelingen", "/wandeling/"), (name(h), route_url(h))]),
    ]
    return page(title, description, route_url(h), body, h.get("image") or f"{SITE}/og-image.jpg", json_ld)


def overview_page(hikes: list[dict]) -> str:
    by_province: dict[str, list[dict]] = {}
    for h in hikes:
        for p in h.get("provinces", []):
            by_province.setdefault(p, []).append(h)
    sections = "".join(
        f'<section id="{e(p)}"><h2>{e(PROVINCE_LABELS.get(p, p))} ({len(hs)})</h2>'
        f'<div class="grid">{"".join(card(h) for h in sorted(hs, key=lambda x: name(x)))}</div></section>'
        for p, hs in sorted(by_province.items(), key=lambda kv: PROVINCE_LABELS.get(kv[0], kv[0]))
    )
    toc = " · ".join(
        f'<a href="#{e(p)}">{e(PROVINCE_LABELS.get(p, p))}</a>'
        for p in sorted(by_province, key=lambda p: PROVINCE_LABELS.get(p, p))
    )
    body = f"""    <h1>Alle {len(hikes)} NS-wandelingen</h1>
    <p class="lead">Wandelroutes die bij een NS-station beginnen en eindigen, per provincie. Met kaart, afstand en GPX-download.</p>
    <p class="toc">{toc}</p>
    {sections}"""
    json_ld = [
        {
            "@type": "ItemList",
            "name": "NS-wandelingen",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "url": SITE + route_url(h), "name": name(h)}
                for i, h in enumerate(hikes, 1)
            ],
        },
        breadcrumb([("Kaart", "/"), ("Wandelingen", "/wandeling/")]),
    ]
    title = f"Alle {len(hikes)} NS-wandelingen per provincie | NS Wandelingen Kaart"
    description = f"Overzicht van alle {len(hikes)} NS-wandelingen in Nederland, per provincie, met afstand, start- en eindstation en GPX-download."
    return page(title, description, "/wandeling/", body, f"{SITE}/og-image.jpg", json_ld)


def sitemap(hikes: list[dict]) -> str:
    urls = ["/", "/wandeling/"] + [route_url(h) for h in hikes]
    entries = "".join(f"  <url><loc>{SITE}{u}</loc></url>\n" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}</urlset>\n'


def main():
    hikes = [h for h in json.loads((BASE / "hikes.json").read_text()) if h.get("gpxFile") and h.get("slug")]
    for h in hikes:
        out = OUT_DIR / h["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(route_page(h, hikes))
    (OUT_DIR / "index.html").write_text(overview_page(hikes))
    (BASE / "sitemap.xml").write_text(sitemap(hikes))
    print(f"wrote {len(hikes)} route pages, wandeling/index.html and sitemap.xml")


if __name__ == "__main__":
    main()
