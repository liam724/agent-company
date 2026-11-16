#!/bin/sh
# One-time setup on a fresh Debian/Ubuntu VM. Run as root: sh install.sh <git-clone-url>
# Afterwards: edit /etc/modelsunset.env, point the domain's A/AAAA records at this VM,
# set the domain in /etc/caddy/Caddyfile, then: systemctl reload caddy
set -eu
REPO="$1"
apt-get update -qq && apt-get install -y -qq python3 git caddy
id modelsunset >/dev/null 2>&1 || useradd --system --home /srv/modelsunset --shell /usr/sbin/nologin modelsunset
mkdir -p /srv/modelsunset /var/lib/modelsunset
[ -d /srv/modelsunset/app ] || git clone --depth 50 "$REPO" /srv/modelsunset/app
chown -R modelsunset: /srv/modelsunset /var/lib/modelsunset
D=/srv/modelsunset/app/product/deploy
[ -f /etc/modelsunset.env ] || { cp $D/env.example /etc/modelsunset.env; chmod 600 /etc/modelsunset.env; }
cp $D/modelsunset-api.service $D/modelsunset-daily.service $D/modelsunset-daily.timer /etc/systemd/system/
cp $D/Caddyfile /etc/caddy/Caddyfile
chmod +x $D/daily.sh
systemctl daemon-reload
systemctl enable --now modelsunset-api.service modelsunset-daily.timer
systemctl start modelsunset-daily.service
systemctl reload caddy
echo "Installed. Edit /etc/modelsunset.env and /etc/caddy/Caddyfile, then restart the services."
