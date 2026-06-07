import time
import uuid
import json
import logging
from typing import Optional, TypedDict

import numpy as np
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.services.config_service import get_top_k_default
from app.services.config_service import get_redis_client
from app.services.explain_service import calculate_sample_weights, generate_explanation
from app.services.milvus_service import VECTOR_DIM, milvus_service


EPSILON = 1e-6
CHECKPOINT_TTL_SECONDS = 3600
logger = logging.getLogger(__name__)


# 这是整个预测流程里会一路传下去的数据。
# 可以把它理解成一个“流程袋子”：每一步往里面放自己的结果。
class PredictionState(TypedDict):
    vector: list[float]
    source_filter: Optional[str]
    top_k: Optional[int]
    similar_samples: list[dict]
    weights: list[float]
    sbp_predicted: Optional[int]
    dbp_predicted: Optional[int]
    confidence: Optional[float]
    explanation: Optional[str]
    error: Optional[str]
    workflow_trace: list[dict]


def retrieve_node(state: PredictionState) -> PredictionState:
    # 第一步：拿当前用户的 PPG 特征向量，去 Milvus 里找相似样本。
    started_at = time.perf_counter()
    logger.info("prediction.retrieve.start top_k=%s source_filter=%s", state.get("top_k"), state.get("source_filter"))
    if len(state["vector"]) != VECTOR_DIM:
        return _with_error(state, f"PPG特征向量维度必须为{VECTOR_DIM}", "retrieve", started_at)

    try:
        top_k = int(state.get("top_k") or get_top_k_default())
        similar_samples = milvus_service.search_similar(
            state["vector"],
            top_k=top_k,
            source=state.get("source_filter"),
        )

        cleaned_samples = [_clean_sample(item) for item in similar_samples]
        if not cleaned_samples:
            return _with_error(state, "特征库为空，未找到相似样本，请联系管理员初始化数据", "retrieve", started_at)

        logger.info("prediction.retrieve.done count=%s", len(cleaned_samples))
        return _with_trace({**state, "similar_samples": cleaned_samples}, "retrieve", started_at, {"count": len(cleaned_samples)})
    except Exception as exc:
        logger.exception("prediction.retrieve.failed")
        return _with_error(state, f"Milvus检索失败: {exc}", "retrieve", started_at)


def predict_node(state: PredictionState) -> PredictionState:
    # 第二步：根据相似样本的血压值做加权平均，得到这次的预测血压。
    started_at = time.perf_counter()
    logger.info("prediction.predict.start sample_count=%s", len(state.get("similar_samples", [])))
    if state.get("error"):
        return state

    try:
        samples = state["similar_samples"]
        if not samples:
            return _with_error(state, "相似样本为空，无法预测血压", "predict", started_at)

        distances = np.asarray([float(item["distance"]) for item in samples], dtype=np.float64)
        sbps = np.asarray([int(item["sbp"]) for item in samples], dtype=np.float64)
        dbps = np.asarray([int(item["dbp"]) for item in samples], dtype=np.float64)
        weights = np.asarray(calculate_sample_weights(samples, epsilon=EPSILON), dtype=np.float64)

        # 距离越近的样本权重越高，所以它们对最终预测影响更大。
        sbp_predicted = int(np.round(float(np.sum(weights * sbps))))
        dbp_predicted = int(np.round(float(np.sum(weights * dbps))))
        if sbp_predicted <= dbp_predicted:
            # 正常情况下收缩压应该大于舒张压，如果算出来不合理，就用中位数兜底。
            sbp_predicted = int(np.median(sbps))
            dbp_predicted = int(np.median(dbps))

        next_state = {
            **state,
            "weights": [float(item) for item in weights],
            "sbp_predicted": sbp_predicted,
            "dbp_predicted": dbp_predicted,
        }
        logger.info("prediction.predict.done sbp=%s dbp=%s", sbp_predicted, dbp_predicted)
        return _with_trace(next_state, "predict", started_at, {"sbp": sbp_predicted, "dbp": dbp_predicted})
    except Exception as exc:
        logger.exception("prediction.predict.failed")
        return _with_error(state, f"预测计算失败: {exc}", "predict", started_at)


def explain_node(state: PredictionState) -> PredictionState:
    # 第三步：给预测结果配一段解释，并算出置信度。
    started_at = time.perf_counter()
    logger.info("prediction.explain.start")
    if state.get("error"):
        return state

    try:
        explanation, metrics = generate_explanation(
            state["similar_samples"],
            state.get("sbp_predicted"),
            state.get("dbp_predicted"),
        )
        confidence = float(metrics.get("confidence") or 0)
        sbp_std = float(metrics.get("sbp_std") or 0)

        next_state = {**state, "confidence": round(confidence, 2), "explanation": explanation}
        logger.info("prediction.explain.done confidence=%s sbp_std=%.2f", round(confidence, 2), sbp_std)
        return _with_trace(next_state, "explain", started_at, {"confidence": round(confidence, 2), "sbp_std": round(sbp_std, 2)})
    except Exception as exc:
        logger.exception("prediction.explain.failed")
        return _with_error(state, f"解释生成失败: {exc}", "explain", started_at)


def build_workflow():
    # 这里把三个步骤串起来：检索 -> 预测 -> 解释。
    workflow = StateGraph(PredictionState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("predict", predict_node)
    workflow.add_node("explain", explain_node)
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "predict")
    workflow.add_edge("predict", "explain")
    workflow.add_edge("explain", END)
    return workflow.compile(checkpointer=MemorySaver())


app = build_workflow()


def run_prediction(
    vector: list[float],
    source_filter: str | None = None,
    top_k: int | None = None,
) -> dict:
    # 外部真正调用的入口。传入一个特征向量，就会跑完整预测流程。
    initial_state: PredictionState = {
        "vector": [float(item) for item in vector],
        "source_filter": source_filter,
        "top_k": top_k,
        "similar_samples": [],
        "weights": [],
        "sbp_predicted": None,
        "dbp_predicted": None,
        "confidence": None,
        "explanation": None,
        "error": None,
        "workflow_trace": [],
    }
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    final_state = app.invoke(initial_state, config=config)
    result = {
        "thread_id": thread_id,
        "sbp": final_state.get("sbp_predicted"),
        "dbp": final_state.get("dbp_predicted"),
        "confidence": final_state.get("confidence"),
        "explanation": final_state.get("explanation"),
        "similar_samples": final_state.get("similar_samples", []),
        "weights": final_state.get("weights", []),
        "workflow_trace": final_state.get("workflow_trace", []),
        "error": final_state.get("error"),
    }
    _write_redis_checkpoint(thread_id, result)
    return result


def _clean_sample(sample: dict) -> dict:
    # Milvus 返回的数据类型可能比较杂，这里统一转成后面好处理的格式。
    return {
        "id": int(sample.get("id", 0)),
        "distance": float(sample.get("distance", 0.0)),
        "sbp": int(sample.get("sbp", 0)),
        "dbp": int(sample.get("dbp", 0)),
        "source": str(sample.get("source", "")),
        "record_id": int(sample.get("record_id", 0) or 0),
        "mock_id": str(sample.get("mock_id", "") or ""),
        "create_time": int(sample.get("create_time", 0) or 0),
    }


def _with_error(state: PredictionState, message: str, node: str, started_at: float) -> PredictionState:
    # 某一步出错时，不直接崩掉，而是把错误信息放回流程结果里。
    return _with_trace({**state, "error": message}, node, started_at, {"error": message})


def _with_trace(state: PredictionState, node: str, started_at: float, extra: dict | None = None) -> PredictionState:
    # 记录每一步用了多久、做了什么，方便前端展示，也方便后端排查问题。
    trace = [
        *state.get("workflow_trace", []),
        {
            "node": node,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            **(extra or {}),
        },
    ]
    return {**state, "workflow_trace": trace}


def _write_redis_checkpoint(thread_id: str, result: dict) -> None:
    # 把本次预测结果临时放到 Redis，后面如果要追踪流程，可以按 thread_id 找到。
    try:
        client = get_redis_client()
        client.setex(f"lg_ckpt:{thread_id}", CHECKPOINT_TTL_SECONDS, json.dumps(result, ensure_ascii=False))
        client.close()
    except Exception:
        logger.exception("Failed to write LangGraph checkpoint to Redis thread_id=%s", thread_id)
