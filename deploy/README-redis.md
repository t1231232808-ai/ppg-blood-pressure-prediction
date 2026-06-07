# Redis 7.2 Local Deployment

This project follows `部署文档/D02-Redis部署.md`.

## Start

```bash
docker compose -f deploy/docker-compose.local.yml up -d redis
```

The Redis service is configured as:

```text
image: redis:7.2
container_name: redis
restart: always
port: 6379
maxmemory: 256mb
maxmemory-policy: allkeys-lru
```

If host port `6379` is already occupied:

```powershell
$env:REDIS_HOST_PORT="6380"
docker compose -f deploy/docker-compose.local.yml up -d redis
```

Then keep `backend/.env` aligned:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## Verify

```bash
docker ps --filter name=redis
docker exec -it redis redis-cli ping
docker exec redis redis-cli CONFIG GET maxmemory
docker exec redis redis-cli CONFIG GET maxmemory-policy
```

Expected:

```text
PONG
maxmemory = 268435456
maxmemory-policy = allkeys-lru
```

## Basic Test

```bash
docker exec -it redis redis-cli
SET test_key "hello"
GET test_key
DEL test_key
EXIT
```

## Operations

```bash
docker logs -f redis
docker exec redis redis-cli INFO memory
docker exec redis redis-cli DBSIZE
docker exec redis redis-cli FLUSHALL
docker restart redis
docker stop redis
```
