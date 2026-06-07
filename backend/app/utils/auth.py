import json
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import User
from app.services.config_service import get_redis_client
from app.utils.jwt_util import decode_access_token
#FastAPI 鉴权依赖（用户登录校验 + Redis 缓存 + 管理员权限拦截）
#接口权限拦截器，通过 Header 的 Bearer Token 解析登录用户，优先走 Redis 缓存减少 MySQL 查询，
#分为普通登录鉴权、管理员鉴权两套依赖，全项目接口通过Depends(get_current_user)实现登录校验

bearer_scheme = HTTPBearer(auto_error=False)      # 解析请求头Authorization: Bearer xxx，关闭内置自动报错
USER_CACHE_TTL_SECONDS = 600       # Redis用户缓存有效期：600秒=10分钟
logger = logging.getLogger(__name__)


def get_current_user(       #通用登录鉴权依赖｜核心函数
    #Depends()是 FastAPI 依赖注入标识，代表这个参数的值由bearer_scheme自动解析生成
    #请求头有Bearer xxx → 生成HTTPAuthorizationCredentials对象
    #请求头没 Authorization 头 / 格式错误 → 因为auto_error=False，不会自动抛 401，直接赋值None
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    user_id = decode_access_token(credentials.credentials)      #JWT 解析 token
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证已失效")
    cached_user = _read_user_cache(user_id)     #优先读取 Redis 缓存（优化：减少 DB 查询）
    if cached_user is not None:     
        if cached_user.status != 1:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
        return cached_user

    user = db.get(User, int(user_id))       # 缓存没命中→查 MySQL 数据库
    if user is None or user.status != 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    _write_user_cache(user)     #查到合法用户→写入 Redis 缓存
    return user

# 管理员权限依赖
def require_admin(user: User = Depends(get_current_user)) -> User:     #先校验必须登录，再校验角色是否为 admin
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def _read_user_cache(user_id: str) -> User | None:      #读 Redis 缓存用户
    try:
        client = get_redis_client()
        raw = client.get(f"user:{user_id}")     #读取 key 为user:1的缓存数据
        client.close()
    except Exception:
        logger.debug("Redis user cache read failed user_id=%s", user_id, exc_info=True)
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)      #反序列化 JSON → 手动构造User对象（只存 id/username/email/role/status，密码 password_hash 填空不缓存）
        return User(
            id=int(data["id"]),
            username=str(data["username"]),
            email=str(data["email"]),
            role=str(data["role"]),
            status=int(data["status"]),
            password_hash="",
        )
    except Exception:
        logger.warning("Invalid cached user payload user_id=%s", user_id, exc_info=True)
        return None


def _write_user_cache(user: User) -> None:      #写入 Redis 用户缓存
    try:
        client = get_redis_client()
        client.setex(       
            f"user:{user.id}",  #key：user:{user.id}
            USER_CACHE_TTL_SECONDS,
            json.dumps(         #序列化用户关键信息为 JSON
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "status": user.status,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                },
                ensure_ascii=False,
            ),
        )
        client.close()
    except Exception:
        logger.debug("Redis user cache write failed user_id=%s", user.id, exc_info=True)
