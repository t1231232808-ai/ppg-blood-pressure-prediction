# FastAPI Backend Docker Deployment

This project follows `部署文档/D04-后端FastAPI部署.md`.

## Image

```text
base image: python:3.11-slim
runtime: gunicorn + uvicorn worker
port: 8000
container: ppg-backend
```

## Production Env

Copy and edit:

```bash
cp backend/.env.production.example backend/.env.production
```

Required production values:

```env
APP_ENV=production
APP_SECRET_KEY=CHANGE_THIS_TO_A_RANDOM_STRING_32CHARS
MYSQL_HOST=mysql
MYSQL_PORT=3306
REDIS_HOST=redis
REDIS_PORT=6379
MILVUS_HOST=milvus-standalone
MILVUS_PORT=19530
FRONTEND_URL=http://your-server-ip
```

`APP_SECRET_KEY` must be changed before production use.

## Build

```bash
cd backend
docker build -t ppg-backend:latest .
```

## Run With Docker

```bash
docker run -d \
  --name ppg-backend \
  --restart always \
  -p 8000:8000 \
  --network milvus-net \
  -v /path/to/project/backend/app/static:/app/app/static \
  ppg-backend:latest
```

If dependencies are running in the same compose network, prefer compose:

```bash
docker compose -f deploy/docker-compose.local.yml up -d backend
```

## Verify

```bash
docker logs -f --tail=100 ppg-backend
curl http://127.0.0.1:8000/api/v1/health
```

Expected health shape:

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "...",
    "services": {
      "mysql": "connected",
      "milvus": "connected",
      "redis": "connected"
    }
  }
}
```

## Operations

```bash
docker logs -f --tail=100 ppg-backend
docker restart ppg-backend
docker exec -it ppg-backend bash
docker exec ppg-backend ps aux
docker stop ppg-backend
```

## Troubleshooting

```bash
docker logs ppg-backend
docker network inspect milvus-net
docker exec -it ppg-backend python -c "from app.config import get_settings; print(get_settings().mysql_host, get_settings().milvus_host)"
```

Common causes:

- Dependency containers are not running.
- `.env` values point to `localhost` inside Docker instead of container names.
- `APP_SECRET_KEY` was not set for production.
- Milvus collection has not been initialized with `python deploy/init_milvus.py`.
