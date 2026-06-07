from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import User
from app.services.record_service import delete_record as delete_record_service
from app.services.record_service import get_record_detail, get_stats, query_records
from app.utils.auth import get_current_user
from app.utils.response import success
# 历史记录管理模块（查询列表 / 统计 / 详情 / 删除）

router = APIRouter()


@router.get("")
def list_records(
    page: int = 1,  #页码，默认第 1 页
    page_size: int = 10,    #每页条数，默认 10 条
    start_date: str | None = None,  #起止日期筛选，不传则查全部时间
    end_date: str | None = None,
    bp_level: list[str] | None = Query(default=None),     #血压等级多选筛选（正常 / 偏高 / 高血压等），Query 实现前端多参数传参
    user: User = Depends(get_current_user), #当前登录用户，用user.id做数据隔离，只查该用户自己的记录
    db: Session = Depends(get_db),
):
    # 调用query_records做分页 + 多条件筛选查询，结果套success()返回前端列表
    return success(query_records(db, user.id, page, page_size, start_date, end_date, bp_level))


@router.get("/stats")
def record_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 统计接口，比如最近 7 天平均血压、预测次数、血压等级分布
    return success(get_stats(db, user.id))


@router.get("/{record_id}")
def record_detail(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 查某一条预测记录的完整详情
    return success(get_record_detail(db, record_id, user))


@router.delete("/{record_id}")
def delete_record(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 删除自己的某条历史记录。
    delete_record_service(db, record_id, user.id)
    return success(message="deleted")
