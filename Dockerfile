FROM nginx:1.27-alpine

COPY index.html hikes.json stations.json railways.geojson og-image.jpg robots.txt sitemap.xml /usr/share/nginx/html/
COPY gpx/ /usr/share/nginx/html/gpx/
COPY assets/ /usr/share/nginx/html/assets/
COPY wandeling/ /usr/share/nginx/html/wandeling/

EXPOSE 80
