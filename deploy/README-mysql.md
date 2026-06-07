# MySQL 8 Local Deployment

This project follows `部署文档/D01-MySQL8部署.md`.

## Start

On Linux, create the persistent directory first:

```bash
sudo mkdir -p /data/mysql
sudo chmod 755 /data/mysql
docker compose -f deploy/docker-compose.local.yml up -d mysql
```

On Windows with Docker Desktop, either allow Docker to create `/data/mysql` inside the Linux VM, or override the host path:

```powershell
$env:MYSQL_DATA_DIR="D:\tcj\mysql-data"
$env:MYSQL_HOST_PORT="3307"
docker compose -f deploy/docker-compose.local.yml up -d mysql
```

Then keep `backend/.env` aligned:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_USER=bp_user
MYSQL_PASSWORD=bp_password
MYSQL_DB=bp_prediction
```

## Verify

```bash
docker ps --filter name=mysql
docker logs -f --tail=100 mysql
docker exec -i mysql mysql -u bp_user -pbp_password bp_prediction -e "SHOW TABLES;"
```

Expected tables:

```text
users
prediction_records
ppg_raw_data
system_configs
```

Default admin:

```text
admin / admin123
```

## Backup And Restore

```bash
docker exec mysql mysqldump -u root -proot_password bp_prediction > backup.sql
docker exec -i mysql mysql -u root -proot_password bp_prediction < backup.sql
```
