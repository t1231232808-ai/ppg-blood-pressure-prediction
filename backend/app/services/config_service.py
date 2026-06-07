from typing import Callable
import logging

from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import SessionLocal
from app.models.entities import SystemConfig

# DB+Redis 双层缓存架构
# 系统关键阈值（信噪比 SNR、置信度、Milvus 查询 nprobe、TopK）存在 MySQLSystemConfig，
# 用 Redis 做热点缓存，不用每次读库；后台管理员接口修改配置、刷新缓存，全配置带数值范围校验

CACHE_TTL_SECONDS = 300          # Redis配置缓存过期时间：5分钟
logger = logging.getLogger(__name__)
CONFIG_RANGES = {
    "top_k_default": (3,10,int),          # 相似返回条数：3~10 整型
    "confidence_threshold": (0.0,1.0,float),# 置信阈值：0~1浮点
    "milvus_nprobe":(1,128,int),          # Milvus检索nprobe：1~128
    "snr_threshold":(5,20,int)            # 信噪比阈值：5~20
}


def get_redis_client(decode_responses: bool = True) -> Redis:   #从项目全局配置读取 host/port/db，创建 Redis 连接
    settings = get_settings()
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=decode_responses,  #自动字符串解码
        socket_timeout=2,   #防卡死
    )


def get_config_value(key: str, default: str) -> str:    #先查 Redis，没有再查 MySQL
    cache_key = _cache_key(key)
    try:
        client = get_redis_client()
        cached = client.get(cache_key)
        client.close()
        if cached is not None:
            return str(cached)
    except Exception:
        logger.debug("Redis config cache read failed key=%s", key, exc_info=True)

    try:
        with SessionLocal() as db:
            value = db.scalar(select(SystemConfig.config_value).where(SystemConfig.config_key == key))
            actual = value if value is not None else default
            _write_config_cache(key, actual)
            return actual
    except Exception:
        logger.warning("Config database read failed key=%s, using default", key, exc_info=True)
        return default


def list_configs(db: Session) -> list[SystemConfig]:
    return db.scalars(select(SystemConfig).order_by(SystemConfig.config_key)).all()


def update_config(db: Session, key: str, value: str) -> SystemConfig:
    config = db.scalar(select(SystemConfig).where(SystemConfig.config_key == key))
    if config is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    validate_config_value(key, value)
    config.config_value = value
    db.commit()
    db.refresh(config)
    _write_config_cache(key, value)
    return config


def refresh_config_cache(db: Session) -> dict:
    configs = list_configs(db)
    refreshed = []
    for config in configs:
        _write_config_cache(config.config_key, config.config_value)
        refreshed.append(config.config_key)
    return {"ttl_seconds": CACHE_TTL_SECONDS, "refreshed_keys": refreshed}


def clear_user_cache(user_id: int) -> None:
    try:
        client = get_redis_client()
        client.delete(f"user:{user_id}")
        client.close()
    except Exception:
        logger.debug("Redis user cache clear failed user_id=%s", user_id, exc_info=True)


def validate_config_value(key: str, value: str) -> None:
    if key not in CONFIG_RANGES:
        return
    minimum, maximum, caster = CONFIG_RANGES[key]
    try:
        numeric = caster(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="配置值必须是数字") from exc
    if numeric < minimum or numeric > maximum:
        raise HTTPException(status_code=422, detail=f"配置值范围应为 {minimum} ~ {maximum}")


def get_int_config(key: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    return _get_numeric_config(key, default, int, minimum, maximum)


def get_float_config(key: str, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    return _get_numeric_config(key, default, float, minimum, maximum)


def get_top_k_default() -> int:
    return get_int_config("top_k_default", get_settings().top_k_default, minimum=3, maximum=10)


def get_snr_threshold() -> float:
    return get_float_config("snr_threshold", 10.0, minimum=5.0, maximum=20.0)


def get_milvus_nprobe() -> int:
    return get_int_config("milvus_nprobe", 16, minimum=1, maximum=128)


def get_confidence_threshold() -> float:
    return get_float_config("confidence_threshold", get_settings().confidence_threshold, minimum=0.0, maximum=1.0)


def _get_numeric_config(key: str, default, caster: Callable, minimum=None, maximum=None):   #通用数值解析函数
    try:
        value = caster(get_config_value(key, str(default))) #拿到字符串配置 → 用caster(int/float)转数字
    except ValueError:
        value = default
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _write_config_cache(key: str, value: str) -> None:  #写入 Redis 缓存
    try:
        client = get_redis_client()
        client.setex(_cache_key(key), CACHE_TTL_SECONDS, value) # 带过期写入，缓存存活 5min
        client.close()
    except Exception:
        logger.debug("Redis config cache write failed key=%s", key, exc_info=True)


def _cache_key(key: str) -> str:    #统一 Redis 缓存 key 前缀：config:snr_threshold、config:confidence_threshold，方便统一管理
    return f"config:{key}"
