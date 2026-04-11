FROM nginx:1.27-alpine

COPY index.html /usr/share/nginx/html/index.html
COPY hikes.json /usr/share/nginx/html/hikes.json
COPY stations.json /usr/share/nginx/html/stations.json
COPY railways.geojson /usr/share/nginx/html/railways.geojson
COPY gpx/ /usr/share/nginx/html/gpx/

EXPOSE 80
