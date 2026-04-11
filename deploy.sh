#!/usr/bin/env bash
set -euo pipefail

# Deploy ns-wandelingen to Cloudflare Pages.
# First-time setup:
#   npx wrangler login
#
# Usage:
#   ./deploy.sh             # production deploy (branch=main)
#   ./deploy.sh preview     # preview deploy on a dated branch

cd "$(dirname "$0")"

PROJECT_NAME="ns-wandelingen"
MODE="${1:-prod}"

if [[ "$MODE" == "preview" ]]; then
  BRANCH="preview-$(date +%Y%m%d-%H%M%S)"
else
  BRANCH="main"
fi

echo "→ Building dist/"
rm -rf dist
mkdir -p dist/gpx
cp index.html hikes.json stations.json railways.geojson dist/
cp gpx/*.gpx dist/gpx/

FILE_COUNT=$(find dist -type f | wc -l | tr -d ' ')
SIZE=$(du -sh dist | cut -f1)
echo "  $FILE_COUNT files, $SIZE"

echo "→ Deploying to Cloudflare Pages (project: $PROJECT_NAME, branch: $BRANCH)"
npx --yes wrangler@latest pages deploy dist \
  --project-name="$PROJECT_NAME" \
  --branch="$BRANCH" \
  --commit-dirty=true
