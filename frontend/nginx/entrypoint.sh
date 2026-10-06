#!/bin/sh
# Pick the container's DNS resolver at start so the same image works on Docker Compose and Railway.
ns=$(awk '/^nameserver/ {print $2; exit}' /etc/resolv.conf)
case "$ns" in
  *:*) ns="[$ns]" ;;
esac
export NGINX_RESOLVER="${NGINX_RESOLVER:-${ns:-127.0.0.11}}"
export PORT="${PORT:-8080}"
export API_UPSTREAM="${API_UPSTREAM:-http://api:8000}"
echo "web: PORT=$PORT API_UPSTREAM=$API_UPSTREAM NGINX_RESOLVER=$NGINX_RESOLVER"
exec /docker-entrypoint.sh nginx -g "daemon off;"
