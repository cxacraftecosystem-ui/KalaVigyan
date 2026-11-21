#!/usr/bin/env bash
set -euxo pipefail

APP=/opt/kalavigyan
PY_VERSION="3.15.2"
PY_BUILD="20261110"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.15.2%2B20261110-x86_64-unknown-linux-gnu-install_only.tar.gz"
PY_SHA256="182e7adf7e4f0e32dafac5143f00d466afd20eef45918ea170f78884e503ac18"
UV_VERSION="0.13.9"
UV_SHA256="a7fbaff2b9a271d85c1bdb540941090fd1ce011797b4abeb48e4dcd39c2471d5"
SEARXNG_IMAGE="docker.io/searxng/searxng:2026.11.15-2d500cb6b"

if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
sysctl -w vm.swappiness=10
echo 'vm.swappiness=10' > /etc/sysctl.d/90-kalavigyan.conf

mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=500M\nSystemKeepFree=2G\n' > /etc/systemd/journald.conf.d/size.conf
systemctl restart systemd-journald

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl gnupg git jq unzip openssl libatomic1 ffmpeg nginx redis-server certbot python3-certbot-nginx

install -m 0755 -d /etc/apt/keyrings
curl -fsSL --retry 5 https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io
systemctl enable --now docker

if ! command -v aws >/dev/null 2>&1; then
  snap install aws-cli --classic
fi

if [ "$(/usr/local/bin/uv --version 2>/dev/null | awk '{print $2}')" != "$UV_VERSION" ]; then
  t="$(mktemp -d)"
  curl -fsSL --retry 5 -o "$t/uv.tar.gz" "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz"
  echo "${UV_SHA256}  $t/uv.tar.gz" | sha256sum -c -
  tar -xzf "$t/uv.tar.gz" -C "$t" --strip-components=1
  install -m 0755 "$t/uv" "$t/uvx" /usr/local/bin/
  rm -rf "$t"
fi

py_home="/opt/cpython/${PY_VERSION}+${PY_BUILD}"
if [ ! -e "$py_home" ]; then
  install -d -o root -g root -m 0755 /opt/cpython
  stage="$(mktemp -d /opt/cpython/.incoming.XXXXXX)"
  curl -fsSL --proto '=https' --tlsv1.2 --retry 5 --retry-delay 10 --retry-all-errors --connect-timeout 30 --max-time 900 -o "$stage/python.tar.gz" "$PY_URL"
  echo "${PY_SHA256}  $stage/python.tar.gz" | sha256sum -c -
  tar -xzf "$stage/python.tar.gz" -C "$stage" --no-same-owner
  "$stage/python/bin/python${PY_VERSION%.*}" -I -m compileall -q "$stage/python/lib/python${PY_VERSION%.*}" || true
  chown -R root:root "$stage/python"
  chmod -R go-w "$stage/python"
  mv -T "$stage/python" "$py_home"
  rm -rf "$stage"
fi
"$py_home/bin/python${PY_VERSION%.*}" -I -c 'import sys, platform, ssl, sqlite3, venv; assert platform.python_version() == sys.argv[1]; print("CPython", platform.python_version(), ssl.OPENSSL_VERSION)' "$PY_VERSION"

install -d -m 0755 /etc/kalavigyan
cat > /etc/kalavigyan/box.env <<BOX
KV_PYTHON=${py_home}/bin/python${PY_VERSION%.*}
KV_APP=${APP}
KV_REGION=ap-south-1
KV_ENV_PATH=/kalavigyan/env
BOX

if ! id kalavigyan >/dev/null 2>&1; then
  useradd --system --home-dir "$APP" --shell /usr/sbin/nologin kalavigyan
fi
install -d -o root -g kalavigyan -m 0755 "$APP" "$APP/releases"
install -d -o kalavigyan -g kalavigyan -m 0750 "$APP/state"
[ -f "$APP/.env" ] || install -o root -g kalavigyan -m 0640 /dev/null "$APP/.env"
[ -f "$APP/fetcher.env" ] || install -o root -g kalavigyan -m 0640 /dev/null "$APP/fetcher.env"

sed -i -E 's/^#?\s*maxmemory .*/maxmemory 256mb/; s/^#?\s*maxmemory-policy .*/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
grep -q '^maxmemory ' /etc/redis/redis.conf || echo 'maxmemory 256mb' >> /etc/redis/redis.conf
grep -q '^maxmemory-policy ' /etc/redis/redis.conf || echo 'maxmemory-policy allkeys-lru' >> /etc/redis/redis.conf
systemctl enable redis-server
systemctl restart redis-server

cat > /etc/nginx/conf.d/kalavigyan-proto.conf <<'NGINX'
map $http_cloudfront_forwarded_proto $kv_forwarded_proto {
    default $scheme;
    https https;
}
NGINX

cat > /etc/nginx/sites-available/kalavigyan <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    client_max_body_size 200M;
    include /etc/nginx/snippets/kalavigyan-origin-verify.conf;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $kv_forwarded_proto;
        proxy_buffering off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
NGINX
if [ ! -s /etc/nginx/snippets/kalavigyan-origin-verify.conf ]; then
  printf 'allow 127.0.0.1;\nallow ::1;\ndeny all;\n' > /etc/nginx/snippets/kalavigyan-origin-verify.conf
fi
ln -sf /etc/nginx/sites-available/kalavigyan /etc/nginx/sites-enabled/kalavigyan
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx

install -d -m 0755 /etc/searxng
if [ ! -f /etc/searxng/settings.yml ]; then
  cat > /etc/searxng/settings.yml <<YAML
use_default_settings: true
general:
  instance_name: "kalavigyan"
server:
  secret_key: "$(openssl rand -hex 32)"
  limiter: false
  image_proxy: false
  public_instance: false
search:
  safe_search: 1
  formats:
    - html
    - json
YAML
fi
chown -R 977:977 /etc/searxng
chmod 0750 /etc/searxng
chmod 0640 /etc/searxng/settings.yml
docker pull "$SEARXNG_IMAGE"
docker rm -f searxng >/dev/null 2>&1 || true
docker run -d --name searxng --restart unless-stopped \
  --memory 768m --pids-limit 256 \
  -p 127.0.0.1:8888:8080 \
  -v /etc/searxng:/etc/searxng \
  -e SEARXNG_BASE_URL=http://127.0.0.1:8888/ \
  "$SEARXNG_IMAGE"

echo "kalavigyan box ready"
