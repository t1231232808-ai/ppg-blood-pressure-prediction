from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import User
from app.models.schemas import TokenOut, UserCreate, UserLogin, UserOut
from app.utils.auth import get_current_user
from app.utils.jwt_util import create_access_token, hash_password, verify_password
from app.utils.response import success


router = APIRouter()


@router.post("/register")
def register(payload: UserCreate, db: Session = Depends(get_db)):   #前端 POST JSON，由 Pydantic 自动校验用户名 / 邮箱 / 密码格式
    # 注册接口：先看用户名或邮箱有没有被用过，没有的话就创建新用户。
    exists = db.scalar(select(User).where(or_(User.username == payload.username, User.email == payload.email)))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名或邮箱已存在")
    # 密码不会直接存明文，而是先做哈希处理再存进数据库。
    user = User(username=payload.username, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    #model_validate(user)：把数据库 ORM 对象 → 转换成 Pydantic 模型实例，自动过滤掉 password_hash 等敏感字段
    #只保留 UserOut 里定义的 id/username/email/role/status/created_at
    #.model_dump()：Pydantic 实例调用该方法，把 Pydantic 对象转为 Python 字典 dict，方便转 JSON 返回前端
    return success(UserOut.model_validate(user).model_dump())


@router.post("/login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    # 登录接口：按用户名找用户，然后校验密码。
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.status != 1:
        # 管理员可以禁用用户，被禁用的人就不能继续登录。
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    token = create_access_token(str(user.id))       #把用户 id 塞进 token，有效期 24h
    # 转成字典后再返回，前端拿到的就是干净的 JSON 数据。
    data = TokenOut(access_token=token, user=UserOut.model_validate(user)).model_dump()
    return success(data)


@router.post("/logout")
def logout():
    # JWT 无状态：后端不存 token，无法作废令牌，逻辑只返回提示
    return success(message="logged out")


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    # 根据 token 拿当前登录用户的信息
    return success(UserOut.model_validate(user).model_dump())
