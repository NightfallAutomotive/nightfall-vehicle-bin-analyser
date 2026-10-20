#!/bin/sh
# Run the analyser on this computer and put it online through a Cloudflare
# Tunnel, as systemd user services that start when you log in.
#
#   deploy/install-home-server.sh                       install, quick tunnel
#   deploy/install-home-server.sh --hostname bin.my.uk  install, fixed address
#   deploy/install-home-server.sh --remove              stop and uninstall
#
# A quick tunnel needs no Cloudflare account, but its trycloudflare.com
# address changes every time it starts. --hostname gives a fixed address on a
# domain in your Cloudflare account; the first run opens a browser login.
#
# Needs: python3, cloudflared (e.g. `brew install cloudflared`).
# The analyser listens on 127.0.0.1 only, so the tunnel is the only way in.
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
UNITS="$HOME/.config/systemd/user"
LIBRARY="${NIGHTFALL_ORI_LIBRARY:-$HOME/.local/share/nightfall-bin-analyser/library}"
PORT="${NIGHTFALL_PORT:-8000}"
CLOUDFLARED=$(command -v cloudflared || echo /home/linuxbrew/.linuxbrew/bin/cloudflared)
TUNNEL=nightfall-bin-analyser
PUBLIC_HOST=""
[ "${1:-}" = "--hostname" ] && PUBLIC_HOST="${2:?--hostname needs an address, e.g. bin.example.co.uk}"

if [ "${1:-}" = "--remove" ]; then
    systemctl --user disable --now nightfall-tunnel.service nightfall-bin-analyser.service 2>/dev/null || true
    rm -f "$UNITS/nightfall-tunnel.service" "$UNITS/nightfall-bin-analyser.service"
    systemctl --user daemon-reload
    echo "Removed. The library at $LIBRARY was left in place."
    exit 0
fi

[ -x "$CLOUDFLARED" ] || { echo "cloudflared not found; install it first (brew install cloudflared)"; exit 1; }

if [ ! -x "$REPO/.venv/bin/uvicorn" ]; then
    python3 -m venv "$REPO/.venv"
    "$REPO/.venv/bin/pip" install -q -r "$REPO/requirements.txt"
fi
mkdir -p "$UNITS" "$LIBRARY"
# The sandbox needs real paths, not ones through the /home link
REPO=$(realpath "$REPO")
LIBRARY=$(realpath "$LIBRARY")

cat > "$UNITS/nightfall-bin-analyser.service" <<EOF
[Unit]
Description=Nightfall BIN Analyser

[Service]
WorkingDirectory=$REPO
Environment=NIGHTFALL_ORI_LIBRARY=$LIBRARY
ExecStart=$REPO/.venv/bin/uvicorn app:app --host 127.0.0.1 --port $PORT
Restart=on-failure

# Sandbox: hide the home folders (on Fedora Atomic /home is a link to
# /var/home), then let back in only the code (read-only) and the library
# (read-write). The rest of the system is read-only.
PrivateUsers=yes
TemporaryFileSystem=/var/home:ro /root:ro
BindReadOnlyPaths=$REPO
BindPaths=$LIBRARY
ProtectSystem=strict
PrivateTmp=yes
NoNewPrivileges=yes
RestrictSUIDSGID=yes
LockPersonality=yes
RestrictNamespaces=yes
RestrictRealtime=yes
SystemCallArchitectures=native
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
UMask=0077
# Python can't write .pyc files into the read-only code folder; that's fine
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=default.target
EOF

if [ -n "$PUBLIC_HOST" ]; then
    # Named tunnel: log in once, create the tunnel once, point the address at it
    [ -f "$HOME/.cloudflared/cert.pem" ] || "$CLOUDFLARED" tunnel login
    "$CLOUDFLARED" tunnel info "$TUNNEL" >/dev/null 2>&1 || "$CLOUDFLARED" tunnel create "$TUNNEL"
    TUNNEL_ID=$("$CLOUDFLARED" tunnel list --output json | python3 -c "
import json, sys
print(next(t['id'] for t in json.load(sys.stdin) if t['name'] == '$TUNNEL'))")
    "$CLOUDFLARED" tunnel route dns --overwrite-dns "$TUNNEL" "$PUBLIC_HOST"
    CONFIG="$HOME/.cloudflared/$TUNNEL.yml"
    cat > "$CONFIG" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json
ingress:
  - hostname: $PUBLIC_HOST
    service: http://127.0.0.1:$PORT
  - service: http_status:404
EOF
    TUNNEL_CMD="$CLOUDFLARED tunnel --no-autoupdate --config $CONFIG run"
else
    TUNNEL_CMD="$CLOUDFLARED tunnel --no-autoupdate --url http://127.0.0.1:$PORT"
fi

cat > "$UNITS/nightfall-tunnel.service" <<EOF
[Unit]
Description=Cloudflare Tunnel for the Nightfall BIN Analyser
After=nightfall-bin-analyser.service network-online.target
Requires=nightfall-bin-analyser.service

[Service]
ExecStart=$TUNNEL_CMD
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable nightfall-bin-analyser.service nightfall-tunnel.service
systemctl --user restart nightfall-bin-analyser.service nightfall-tunnel.service

if [ -n "$PUBLIC_HOST" ]; then
    echo "Analyser: http://127.0.0.1:$PORT"
    echo "Public:   https://$PUBLIC_HOST (DNS can take a few minutes the first time)"
    exit 0
fi

echo "Waiting for the tunnel address..."
for _ in $(seq 1 30); do
    URL=$(journalctl --user -u nightfall-tunnel.service --since "-2min" -o cat 2>/dev/null \
        | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
    [ -n "$URL" ] && break
    sleep 1
done
echo "Analyser: http://127.0.0.1:$PORT"
echo "Public:   ${URL:-not ready yet; run: journalctl --user -u nightfall-tunnel | grep trycloudflare}"
