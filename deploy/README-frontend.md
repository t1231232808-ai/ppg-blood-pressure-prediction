# Vue 3 Frontend Nginx Deployment

This project follows `部署文档/D05-前端Nginx部署.md`.

## Production Env

`frontend/.env.production`:

```env
VITE_API_BASE_URL=/api/v1
```

The frontend calls `/api/v1`; Nginx proxies `/api/` to `http://ppg-backend:8000/api/`.

## Build Static Files

```bash
cd frontend
npm install
npm run build
```

Expected output:

```text
dist/index.html
dist/assets/
```

## Nginx Config

Project-level copy:

```text
deploy/nginx.conf
```

Docker build copy:

```text
frontend/deploy/nginx.conf
```

Features:

- Vue Router history fallback via `try_files`
- `/api/` reverse proxy to `ppg-backend:8000`
- 1-year immutable cache for hashed assets
- Gzip compression
- WebSocket headers reserved for future use

## Build Image

```bash
cd frontend
docker build -t ppg-frontend:latest .
```

## Run

```bash
docker run -d \
  --name ppg-frontend \
  --restart always \
  -p 80:80 \
  --network milvus-net \
  ppg-frontend:latest
```

Or use compose:

```bash
docker compose -f deploy/docker-compose.local.yml up -d frontend
```

If host port `80` is occupied:

```powershell
$env:FRONTEND_HOST_PORT="8080"
docker compose -f deploy/docker-compose.local.yml up -d frontend
```

## Verify

```bash
docker ps --filter name=ppg-frontend
curl -I http://127.0.0.1
curl http://127.0.0.1/api/v1/health
```

Browser:

```text
http://your-server-ip/
```

Expected:

- Login page renders normally
- No static asset 404
- Refreshing nested routes works
- `/api/v1/health` returns backend JSON through Nginx

## Operations

```bash
docker logs -f ppg-frontend
docker exec ppg-frontend cat /var/log/nginx/access.log
docker exec ppg-frontend cat /var/log/nginx/error.log
docker restart ppg-frontend
docker exec ppg-frontend nginx -s reload
docker stop ppg-frontend
```
