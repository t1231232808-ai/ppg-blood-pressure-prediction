from datetime import datetime, timezone
import logging

from fastapi import APIRouter
from pymilvus import connections, utility
from redis import Redis
from sqlalchemy import text

from app.config import get_settings
from app.models.database import SessionLocal
from app.utils.response import success


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    checks = {
        "mysql": _check_mysql(),
        "milvus": _check_milvus(),
        "redis": _check_redis(),
    }
    services = {key: value["status"] for key, value in checks.items()}
    detailed_services = {
        **checks,
        "backend": {"status": "connected", "message": "服务正常"},
    }
    overall = "healthy" if all(status == "connected" for status in services.values()) else "degraded"
    return success(
        {
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "services": services,
            "service_details": detailed_services,
        }
    )


@router.get("/health/db")
def db_health_check():
    return success(_check_mysql())


@router.get("/health/milvus")
def milvus_health_check():
    return success(_check_milvus())


@router.get("/health/redis")
def redis_health_check():
    return success(_check_redis())


def _connected(message: str = "connected") -> dict[str, str]:
    return {"status": "connected", "message": message}


def _disconnected(error: Exception) -> dict[str, str]:
    return {"status": "disconnected", "message": str(error)}


def _check_mysql() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))    # 执行一条最简单SQL探测连通
        return _connected("MySQL connected")
    except Exception as exc:
        logger.warning("MySQL health check failed", exc_info=True)
        return _disconnected(exc)


def _check_milvus() -> dict[str, str]:
    settings = get_settings()
    alias = "health_check"
    try:
        connections.connect(alias=alias, host=settings.milvus_host, port=str(settings.milvus_port))
        utility.has_collection(settings.milvus_collection, using=alias)  # 测试集合是否存在
        connections.disconnect(alias=alias)
        return _connected("Milvus connected")
    except Exception as exc:
        try:
            connections.disconnect(alias=alias) # 异常也要关闭连接，避免连接泄漏
        except Exception:
            logger.debug("Milvus health-check disconnect failed alias=%s", alias, exc_info=True)
        logger.warning("Milvus health check failed", exc_info=True)
        return _disconnected(exc)


def _check_redis() -> dict[str, str]:
    settings = get_settings()
    try:
        client = Redis(host=settings.redis_host, port=settings.redis_port, db=settings.redis_db, socket_timeout=2)
        client.ping()       # redis心跳命令，返回PONG即正常
        client.close()
        return _connected("Redis connected")
    except Exception as exc:
        logger.warning("Redis health check failed", exc_info=True)
        return _disconnected(exc)
