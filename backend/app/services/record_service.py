import json
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from app.services.feature_extraction import encode_vector
from app.services.milvus_service import search_similar
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import PpgRawData, PredictionRecord, User
from app.services.config_service import get_confidence_threshold
from app.services.explain_service import blood_pressure_level, build_explainability, generate_explanation
from app.services.mock_data_service import read_mock_signal
#预测记录数据库 CRUD 业务层
#（MySQL 记录表PredictionRecord+PpgRawData，对接前面历史列表 / 详情 / 统计 / 删除接口）
#整体功能：实现预测记录入库、分页筛选查询、单条详情、统计汇总、删除记录；详情页实时重跑相似检索、补全波形、重新生成解释文案

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


def save_prediction(    #预测结果入库
    db: Session,
    user_id: int,
    filename: str,
    sbp: int,
    dbp: int,
    confidence: float,
    similar_samples: list[dict],
    explanation: str,
    raw_signal: list[float],
    signal_quality: dict | None = None,
    weights: list[float] | None = None,
    workflow_trace: list[dict] | None = None,
) -> int:
    # 预测结束后，把预测值、解释、原始 PPG 波形一起保存下来。
    similar_count = len(similar_samples)
    avg_distance = sum(float(item["distance"]) for item in similar_samples) / similar_count if similar_count else None
    record = PredictionRecord(
        user_id=user_id,
        filename=filename,
        sbp_predicted=int(sbp),
        dbp_predicted=int(dbp),
        confidence=float(confidence),
        similar_count=similar_count,
        avg_distance=round(avg_distance, 4) if avg_distance is not None else None,
        explanation=explanation,
        created_at=datetime.now(SHANGHAI_TZ).replace(tzinfo=None),
    )
    db.add(record)
    db.flush()
    db.add(PpgRawData(record_id=record.id, signal_json=json.dumps(raw_signal), sample_rate=125, duration=10.0))
    db.commit()
    db.refresh(record)
    return int(record.id)


def query_records(      #分页查用户历史记录
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
    bp_level: list[str] | None = None,
) -> dict:
    # 查询某个用户的历史预测记录，支持分页、日期筛选和血压等级筛选。
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    stmt = _apply_record_filters(select(PredictionRecord), user_id, start_date, end_date, bp_level)
    total_stmt = _apply_record_filters(select(func.count()).select_from(PredictionRecord), user_id, start_date, end_date, bp_level)
    records = db.scalars(stmt.order_by(PredictionRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    threshold = get_confidence_threshold()
    return {
        "items": [_record_list_item(item, threshold) for item in records],
        "total": db.scalar(total_stmt) or 0,
        "page": page,
        "page_size": page_size,
    }


def get_record_detail(db: Session, record_id: int, user: User) -> dict:
    # 查单条预测详情。普通用户只能看自己的记录，管理员可以看所有人的。
    record = db.get(PredictionRecord, record_id)
    if record is None or (record.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="记录不存在")
    raw_signal = []
    if record.raw_data:
        raw_signal = json.loads(record.raw_data.signal_json)
    # 详情页会重新找一遍相似样本，并尽量把对应波形也带回去。
    similar_items = _attach_similar_waveforms(db, _search_similar_for_record(raw_signal))
    weights = []
    workflow_trace = []
    explanation_text, explanation_metrics = generate_explanation(similar_items, record.sbp_predicted, record.dbp_predicted)
    threshold = get_confidence_threshold()
    confidence = float(record.confidence)
    return {
        "id": record.id,
        "record_id": record.id,
        "filename": record.filename,
        "sbp": record.sbp_predicted,
        "dbp": record.dbp_predicted,
        "confidence": confidence,
        "confidence_threshold": threshold,
        "is_low_confidence": confidence < threshold,
        "bp_level": blood_pressure_level(record.sbp_predicted, record.dbp_predicted),
        "blood_pressure_level": blood_pressure_level(record.sbp_predicted, record.dbp_predicted),
        "explanation": record.explanation or explanation_text,
        "explanation_metrics": explanation_metrics,
        "similar_count": record.similar_count,
        "avg_distance": float(record.avg_distance) if record.avg_distance is not None else None,
        "created_at": record.created_at,
        "raw_signal": raw_signal,
        "ppg_signal": raw_signal,
        "similar_samples": similar_items,
        "weights": weights,
        "workflow_trace": workflow_trace,
        "explainability": build_explainability(similar_items, weights, workflow_trace),
        "signal_quality": {},
    }


def get_stats(db: Session, user_id: int) -> dict:
    # 给首页或统计页用的汇总数据，比如最近 7 天平均血压、等级分布。
    all_records = db.scalars(select(PredictionRecord).where(PredictionRecord.user_id == user_id)).all()
    since = datetime.now() - timedelta(days=6)
    recent_records = [item for item in all_records if item.created_at >= since.replace(hour=0, minute=0, second=0, microsecond=0)]
    distribution = {"normal": 0, "elevated": 0, "hypertension": 0}
    for record in all_records:
        distribution[blood_pressure_level(record.sbp_predicted, record.dbp_predicted)] += 1

    buckets: dict[str, dict[str, Any]] = {}
    for record in recent_records:
        day = record.created_at.strftime("%Y-%m-%d")
        buckets.setdefault(day, {"date": day, "sbp_values": [], "dbp_values": []})
        buckets[day]["sbp_values"].append(record.sbp_predicted)
        buckets[day]["dbp_values"].append(record.dbp_predicted)

    recent_7days = []
    for offset in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
        bucket = buckets.get(day, {"date": day, "sbp_values": [], "dbp_values": []})
        sbps = bucket["sbp_values"]
        dbps = bucket["dbp_values"]
        recent_7days.append(
            {
                "date": day,
                "avg_sbp": round(sum(sbps) / len(sbps), 1) if sbps else None,
                "avg_dbp": round(sum(dbps) / len(dbps), 1) if dbps else None,
                "min_sbp": min(sbps) if sbps else None,
                "max_sbp": max(sbps) if sbps else None,
                "min_dbp": min(dbps) if dbps else None,
                "max_dbp": max(dbps) if dbps else None,
            }
        )
    recent_sbps = [item.sbp_predicted for item in recent_records]
    recent_dbps = [item.dbp_predicted for item in recent_records]
    return {
        "total_predictions": len(all_records),
        "count": len(recent_records),
        "avg_sbp": round(sum(recent_sbps) / len(recent_sbps), 1) if recent_sbps else 0,
        "avg_dbp": round(sum(recent_dbps) / len(recent_dbps), 1) if recent_dbps else 0,
        "recent_7days_summary": {
            "avg_sbp": round(sum(recent_sbps) / len(recent_sbps), 1) if recent_sbps else None,
            "avg_dbp": round(sum(recent_dbps) / len(recent_dbps), 1) if recent_dbps else None,
            "min_sbp": min(recent_sbps) if recent_sbps else None,
            "max_sbp": max(recent_sbps) if recent_sbps else None,
            "min_dbp": min(recent_dbps) if recent_dbps else None,
            "max_dbp": max(recent_dbps) if recent_dbps else None,
        },
        "recent_7days": recent_7days,
        "level_distribution": distribution,
    }


def delete_record(db: Session, record_id: int, user_id: int) -> None:
    # 删除自己的某条预测记录。
    record = db.get(PredictionRecord, record_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(record)
    db.commit()


def _apply_record_filters(stmt, user_id: int, start_date: str | None, end_date: str | None, bp_level: list[str] | None):
    # 动态拼接 SQL 筛选条件（列表接口多条件过滤）
    stmt = stmt.where(PredictionRecord.user_id == user_id)
    if start_date:
        stmt = stmt.where(PredictionRecord.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        stmt = stmt.where(PredictionRecord.created_at < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    if bp_level:
        conditions = []
        if "normal" in bp_level:
            conditions.append((PredictionRecord.sbp_predicted < 120) & (PredictionRecord.dbp_predicted < 80))
        if "elevated" in bp_level:
            conditions.append(
                (PredictionRecord.sbp_predicted < 140)
                & (PredictionRecord.dbp_predicted < 90)
                & ((PredictionRecord.sbp_predicted >= 120) | (PredictionRecord.dbp_predicted >= 80))
            )
        if "hypertension" in bp_level:
            conditions.append((PredictionRecord.sbp_predicted >= 140) | (PredictionRecord.dbp_predicted >= 90))
        if conditions:
            stmt = stmt.where(or_(*conditions))
    return stmt


def _record_list_item(record: PredictionRecord, threshold: float) -> dict:
    # 数据库记录→前端列表字典格式化
    confidence = float(record.confidence)
    return {
        "id": record.id,
        "filename": record.filename,
        "sbp_predicted": record.sbp_predicted,
        "dbp_predicted": record.dbp_predicted,
        "sbp": record.sbp_predicted,
        "dbp": record.dbp_predicted,
        "confidence": confidence,
        "confidence_threshold": threshold,
        "is_low_confidence": confidence < threshold,
        "similar_count": record.similar_count,
        "avg_distance": float(record.avg_distance) if record.avg_distance is not None else None,
        "bp_level": blood_pressure_level(record.sbp_predicted, record.dbp_predicted),
        "created_at": record.created_at,
    }


def _search_similar_for_record(raw_signal: list[float]) -> list[dict]:
    # 用这条记录自己的波形再去查一次相似样本。
    if not raw_signal:
        return []
    try:
        return search_similar(encode_vector(raw_signal))
    except Exception:
        logger.warning("Failed to search similar samples for record detail", exc_info=True)
        return []


def _attach_similar_waveforms(db: Session, similar_items: list[dict]) -> list[dict]:
    # 相似样本只有血压和距离还不够，这里尽量补上它们的原始波形。
    for item in similar_items:
        signal = _find_signal_for_sample(db, item)
        if signal:
            item["signal"] = signal
    return similar_items


def _find_signal_for_sample(db: Session, sample: dict) -> list[float]:
    # 根据样本来源找到对应波形：模拟数据从文件读，用户上传数据从数据库读。
    if sample.get("source") == "mock":
        mock_id = sample.get("mock_id") or ""
        if mock_id.startswith("mock_"):
            return read_mock_signal(mock_id)
        return []

    record_id = int(sample.get("record_id") or 0)
    if record_id <= 0:
        return []
    record = db.get(PredictionRecord, record_id)
    if record and record.raw_data:
        try:
            return json.loads(record.raw_data.signal_json)
        except json.JSONDecodeError:
            return []
    return []
