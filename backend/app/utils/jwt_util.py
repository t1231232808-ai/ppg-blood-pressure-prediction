from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings
# 密码加密 + JWT 令牌工具模块（用户登录鉴权核心）

ALGORITHM = "HS256"     # JWT加密算法：HS256对称加密
ACCESS_TOKEN_EXPIRE_HOURS = 24      # Token有效期24小时
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")       # 指定用bcrypt做密码哈希


def hash_password(password: str) -> str:        #明文密码→哈希密文（用户注册用）
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:     #密码校验（用户登录用）
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str) -> str:       #生成登录 Token
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": subject, "exp": expire}       # sub=用户唯一标识(一般存user.id)，exp=过期时间
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)
    #把载荷 (payload) + 密钥 + 加密算法，加密生成一段字符串（就是前端要用的 access_token）


def decode_access_token(token: str) -> str | None:      #解析 Token，获取用户 ID
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
        return payload.get("sub")       # 返回user_id字符串
    except JWTError:        # token过期/篡改/格式错误全捕获
        return None
