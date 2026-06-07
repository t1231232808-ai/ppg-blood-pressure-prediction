# Milvus 2.4 Standalone Deployment

This project follows `部署文档/D03-Milvus部署.md`.

## Components

```text
etcd:    quay.io/coreos/etcd:v3.5.5
MinIO:   minio/minio:RELEASE.2023-03-20T20-16-18Z
Milvus:  milvusdb/milvus:v2.4.1
network: milvus-net
```

## Prepare Directories

Linux:

```bash
sudo mkdir -p /data/milvus/etcd /data/milvus/minio
sudo chmod -R 755 /data/milvus
```

Windows Docker Desktop override example:

```powershell
$env:MILVUS_ETCD_DATA_DIR="D:\tcj\milvus-data\etcd"
$env:MILVUS_MINIO_DATA_DIR="D:\tcj\milvus-data\minio"
```

## Start

```bash
docker compose -f deploy/docker-compose.local.yml up -d etcd minio milvus
```

Containers:

```text
milvus-etcd
milvus-minio
milvus-standalone
```

Ports:

```text
2379/2380: etcd
9000: MinIO API
9001: MinIO console
19530: Milvus gRPC
9091: Milvus metrics
```

If `19530` is occupied:

```powershell
$env:MILVUS_GRPC_PORT="19531"
docker compose -f deploy/docker-compose.local.yml up -d etcd minio milvus
```

Then align `backend/.env`:

```env
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=ppg_vectors
```

## Verify Connection

```bash
python -c "from pymilvus import connections, utility; connections.connect(alias='default', host='127.0.0.1', port='19530'); print('Milvus version:', utility.get_server_version())"
```

MinIO console:

```text
http://localhost:9001
minioadmin / minioadmin
```

## Initialize Collection And Mock Data

Run after Milvus is ready:

```bash
python deploy/init_milvus.py
```

The script:

1. Creates `ppg_vectors`
2. Creates `IVF_FLAT` index with `metric_type=L2`, `nlist=128`
3. Generates 500 mock PPG samples
4. Fits PCA model and saves `backend/app/static/pca_model.pkl`
5. Inserts 500 vectors

Verify row count:

```bash
python -c "from pymilvus import connections, Collection; connections.connect(alias='default', host='127.0.0.1', port='19530'); c=Collection('ppg_vectors'); c.load(); print('Row count:', c.num_entities)"
```

Expected:

```text
Row count: 500
```

## Operations

```bash
docker logs -f --tail=100 milvus-standalone
docker logs -f --tail=50 milvus-etcd
docker logs -f --tail=50 milvus-minio
docker restart milvus-standalone
docker stop milvus-standalone milvus-minio milvus-etcd
docker start milvus-etcd milvus-minio milvus-standalone
```
