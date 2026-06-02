#!/bin/sh
set -eu

: "${PORT:=80}"
: "${BACKEND_UPSTREAM_URL:=http://backend:8000}"

envsubst '${PORT} ${BACKEND_UPSTREAM_URL}' \
  < /opt/documind/nginx.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
