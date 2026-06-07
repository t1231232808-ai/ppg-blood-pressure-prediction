#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

mkdir -p /data/mysql /data/milvus/etcd /data/milvus/minio

docker compose -f docker-compose.local.yml up -d mysql redis etcd minio milvus

echo "Waiting for Milvus to start..."
sleep 20

docker compose -f docker-compose.local.yml up -d backend frontend

echo "Services started."
docker ps --filter "name=mysql" \
  --filter "name=redis" \
  --filter "name=milvus" \
  --filter "name=ppg-backend" \
  --filter "name=ppg-frontend"
