from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import User
from app.models.schemas import ConfigOut, ConfigUpdate, UserOut
from app.services.config_service import clear_user_cache, list_configs as list_system_configs
from app.services.config_service import refresh_config_cache, update_config as update_system_config
from app.services.milvus_init_service import initialize_feature_store
from app.utils.auth import require_admin
from app.utils.response import success

#系统配置 + 用户管理 + Milvus 初始化，全部接口强制Depends(require_admin)= 必须管理员账号才能访问
router = APIRouter()


@router.get("/configs")
def list_configs(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    # 管理员查看系统配置，比如置信度阈值、相似样本数量等。
    configs = list_system_configs(db)
    #ORM 数据库对象批量转为前端规范 JSON，套success返回
    #后台配置页面展示全部可配置项（置信阈值、采样阈值等）
    return success([ConfigOut.model_validate(item).model_dump() for item in configs])


@router.put("/configs/{key}")
def update_config(key: str, payload: ConfigUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    # 管理员修改某个配置项。这里兼容 value 和 config_value 两种字段名。
    value = payload.value if payload.value is not None else payload.config_value
    if value is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="配置值不能为空")
    config = update_system_config(db, key, value)
    return success(ConfigOut.model_validate(config).model_dump())


@router.post("/configs/cache/refresh")
def refresh_configs_cache(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    # 把数据库里的配置重新刷到缓存里，避免修改后还读到旧值。
    return success(refresh_config_cache(db), message="配置缓存已刷新")


@router.post("/milvus/initialize")
def initialize_milvus_features(_: User = Depends(require_admin)):
    # 初始化 Milvus 特征库。通常是第一次部署或重建特征数据时用。
    return success(initialize_feature_store(), message="Milvus 特征库初始化完成")


@router.get("/users")       #用户列表分页 + 筛选
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: str | None = Query(default=None, pattern="^(user|admin)$"),
    status: int | None = Query(default=None, ge=0, le=1),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # 管理员查看用户列表，可以按角色、状态筛选。
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)
    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if status is not None:
        stmt = stmt.where(User.status == status)
        count_stmt = count_stmt.where(User.status == status)
    total = db.scalar(count_stmt) or 0
    # 分页+创建时间倒序
    users = db.scalars(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    # 序列化返回
    return success(
        {
            "items": [UserOut.model_validate(item).model_dump() for item in users],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.put("/users/{user_id}/status")
def update_user_status(user_id: int, status: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    # 管理员启用或禁用用户。
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.status = 1 if status else 0
    db.commit()
    db.refresh(user)
    # 用户信息可能被缓存过，状态变了就要清一下，避免权限判断还用旧数据。
    clear_user_cache(user_id)
    return success(UserOut.model_validate(user).model_dump())
