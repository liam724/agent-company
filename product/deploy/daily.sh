#!/bin/sh
# Pull the latest registry from the repo, rebuild the static site atomically, send due alerts.
set -eu
cd /srv/modelsunset/app
git pull --quiet --ff-only
cd product
python3 -m sunset.registry validate
python3 -m sunset.build /srv/modelsunset/dist.new
rm -rf /srv/modelsunset/dist.old
[ -d /srv/modelsunset/dist ] && mv /srv/modelsunset/dist /srv/modelsunset/dist.old
mv /srv/modelsunset/dist.new /srv/modelsunset/dist
python3 -m sunset.alerts notify
