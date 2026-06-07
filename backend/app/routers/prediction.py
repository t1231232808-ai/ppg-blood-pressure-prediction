import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.entities import User
from app.models.schemas import MockPredictionRequest
from app.services.explain_service import blood_pressure_level
from app.services.feature_extraction import encode_vector
from app.services.config_service import get_confidence_threshold, get_snr_threshold
from app.services.milvus_service import insert_vectors
from app.services.mock_data_service import list_mock_samples, read_mock_csv
from app.services.ppg_preprocess import preprocess_csv
from app.services.prediction_workflow import run_prediction
from app.services.record_service import get_record_detail, save_prediction
from app.utils.auth import get_current_user
from app.utils.exceptions import PPGPreprocessError
from app.utils.response import success
#用户上传 PPG 脉搏 CSV 文件→波形预处理→AI 血压预测→数据落 MySQL + 向量入库 Milvus→格式化结果返回前端；
# 附带 mock 测试接口、历史记录查询

router = APIRouter()    #路由分组，最后在主项目挂载
logger = logging.getLogger(__name__)

# 上传的 CSV 最大允许 5MB，避免用户传特别大的文件把服务拖慢。
MAX_UPLOAD_SIZE = 5 * 1024 * 1024


def _persist_prediction(        #预测结果入库 MySQL 函数
    db: Session,
    user_id: int,
    filename: str,
    ppg_signal: list[float],
    result: dict,
    signal_quality: dict | None = None,
) -> int:       #返回新插入记录的主键record_id，后续用来写入 Milvus 向量库
    # 预测完成后，把结果和原始波形一起存进数据库，方便后面查历史记录。
    return save_prediction(
        db=db,
        user_id=user_id,
        filename=filename,
        sbp=result["sbp"],
        dbp=result["dbp"],
        confidence=result["confidence"],
        similar_samples=result.get("similar_samples", []),
        explanation=result.get("explanation") or "",
        raw_signal=ppg_signal,
        signal_quality=signal_quality,
        weights=result.get("weights", []),
        workflow_trace=result.get("workflow_trace", []),
    )


def _persist_uploaded_vector(record_id: int, vector: list[float], result: dict) -> None:
    # 用户上传的数据如果预测成功，也会写进 Milvus。
    # 这样以后做相似样本检索时，它也能成为参考样本。
    sbp = result.get("sbp")
    dbp = result.get("dbp")
    if sbp is None or dbp is None:
        return      ## 无血压值直接放弃入库

    try:
        insert_vectors([vector], [int(sbp)], [int(dbp)], ["user_upload"], record_ids=[record_id])
    except Exception:
        logger.exception("Failed to persist uploaded vector to Milvus record_id=%s", record_id)


def _format_prediction(record_id: int | None, result: dict) -> dict:
    # 这里把预测结果整理成前端更好用的格式。
    # 比如顺手算出血压等级、是否低置信度等字段。
    confidence = result.get("confidence")
    confidence_threshold = get_confidence_threshold()       # 从配置表读取置信阈值
    return {
        "record_id": record_id,
        "sbp": result.get("sbp"),
        "dbp": result.get("dbp"),
        "confidence": confidence,
        "confidence_threshold": confidence_threshold,
        "is_low_confidence": confidence is not None and float(confidence) < confidence_threshold,
        "explanation": result.get("explanation"),
        "blood_pressure_level": blood_pressure_level(result.get("sbp"), result.get("dbp")),
        "similar_samples": result.get("similar_samples", []),
        "weights": result.get("weights", []),
        "workflow_trace": result.get("workflow_trace", []),
    }


async def _read_upload_csv(file: UploadFile) -> bytes:
    # 上传文件先做最基础的检查：必须是 CSV，大小也不能超过限制。
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="请上传CSV文件")
    content = await file.read()     #异步读文件字节
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="CSV文件大小不能超过5MB")
    return content


def _quality_payload(processed) -> dict:
    # 预处理后会带一些信号质量信息，这里统一整理一下，返回给前端展示
    if processed.quality:
        return processed.quality
    return {
        "snr": processed.snr,       # 信噪比
        "sample_rate": processed.sample_rate,       # 采样率
        "duration": processed.duration,     # 波形时长
        "points": processed.points,     # 采样点数
    }


@router.post("/mock")
def predict_mock(payload: MockPredictionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 这个接口用项目里提前准备好的模拟 PPG 数据来跑预测。
    # 主要方便演示、调试，也能在没有真实上传文件时测试完整流程。
    filename, content = read_mock_csv(payload.mock_id)      # 根据mock_id拿内置CSV
    processed = preprocess_csv(content, snr_threshold=0)        # 预处理波形
    vector = encode_vector(processed.signal)        # 波形转特征向量
    result = run_prediction(vector, source_filter="mock")       # 预测血压
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])        # 预测异常报错
    signal_quality = _quality_payload(processed)
    record_id = _persist_prediction(
        db,
        user.id,
        filename,
        processed.signal,
        result,
        signal_quality=signal_quality,
    )
    data = _format_prediction(record_id, result)
    data["signal_quality"] = signal_quality
    return success(data)


@router.get("/mock/options")
def get_mock_options(user: User = Depends(get_current_user)):
    # 返回所有可选的模拟数据，前端下拉列表会用到。
    return success({"items": list_mock_samples()})


@router.post("/upload")
async def predict_upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 这个接口是真正处理用户上传 CSV 的地方
    # 流程是：读文件 -> 预处理信号 -> 提取向量 -> 跑预测 -> 保存记录
    content = await _read_upload_csv(file)      # 校验文件+读字节
    try:
        processed = preprocess_csv(content, snr_threshold=get_snr_threshold())
    except PPGPreprocessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc      # 波形格式/质量异常抛400
    # 1.原始PPG波形转特征向量
    vector = encode_vector(processed.signal)
    # 2.送入模型预测血压
    result = run_prediction(vector)
    # 3.模型报错则返回422
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    # 4.提取波形质量信息（信噪比、采样率等）
    signal_quality = _quality_payload(processed)
    # 5.预测结果、原始波形存入MySQL两张数据表
    record_id = _persist_prediction(db, user.id, file.filename, processed.signal, result, signal_quality=signal_quality)
    # 6.特征向量存入Milvus向量库（用于后续相似波形检索）
    _persist_uploaded_vector(record_id, vector, result)
    # 7.原始预测结果字典→前端标准返回结构
    data = _format_prediction(record_id, result)
    # 8.把波形质量附加到返回数据里
    data["signal_quality"] = signal_quality
    # 9.统一包装成成功JSON返回前端
    return success(data)


@router.get("/{record_id}")
def get_prediction(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 根据记录 ID 查一次预测的完整详情。
    return success(get_record_detail(db, record_id, user))


@router.get("/{record_id}/similar")
def get_prediction_similar(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 单独拿这条预测对应的相似样本和波形，前端做相似波形展示时会用到
    detail = get_record_detail(db, record_id, user)
    # 组装相似样本、波形数据返回前端
    return success(
        {
            "record_id": record_id,
            "similar_samples": detail["similar_samples"],
            "similar_waveforms": [
                {
                    "id": item.get("id"),
                    "sbp": item.get("sbp"),
                    "dbp": item.get("dbp"),
                    "source": item.get("source"),
                    "signal": item.get("signal", []),
                }
                for item in detail["similar_samples"]
                if item.get("signal")
            ],
            "weights": detail["weights"],
        }
    )
