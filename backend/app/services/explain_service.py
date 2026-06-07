import numpy as np


CONFIDENCE_SCALE = 20.0            # 置信度缩放系数
LOW_CONFIDENCE_THRESHOLD = 0.6     # 低置信阈值：<0.6提示可信度偏低
UNRELIABLE_CONFIDENCE_THRESHOLD = 0.4 # 不可靠阈值：<0.4预测失效
LARGE_SBP_STD = 15.0              # 收缩压标准差>15 → 样本差异过大告警


def blood_pressure_level(sbp: int | None, dbp: int | None) -> str | None:
    if sbp is None or dbp is None:  #美国高血压分级标准
        return None
    if sbp >= 140 or dbp >= 90:
        return "hypertension"
    if sbp >= 120 or dbp >= 80:
        return "elevated"
    return "normal"


def calculate_confidence(samples: list[dict]) -> tuple[float, float]:   #置信度 + 收缩压标准差计算
    sbps = np.asarray([int(item["sbp"]) for item in samples], dtype=np.float64)
    sbp_std = float(np.std(sbps)) if sbps.size else 0.0
    confidence = float(np.clip(1.0 / (1.0 + sbp_std / CONFIDENCE_SCALE), 0.0, 1.0))
    return round(confidence, 2), sbp_std


def calculate_sample_weights(samples: list[dict], epsilon: float = 1e-6) -> list[float]:    #相似样本权重
    if not samples:
        return []
    distances = np.asarray([float(item["distance"]) for item in samples], dtype=np.float64)
    weights = 1.0 / (distances + epsilon)
    weights = weights / (float(np.sum(weights)) + epsilon)
    return [float(item) for item in weights]


def generate_explanation(samples: list[dict], sbp_pred: int | None, dbp_pred: int | None) -> tuple[str, dict]:      #生成自然语言解释
    if not samples:
        return "未检索到可用于解释的相似样本。", {
            "sample_count": 0,
            "avg_distance": None,
            "sbp_std": None,
            "closest_sample": None,
            "confidence_level": "unavailable",
        }

    confidence, sbp_std = calculate_confidence(samples)
    distances = [float(item["distance"]) for item in samples]
    avg_distance = float(np.mean(distances))
    closest = min(samples, key=lambda item: float(item["distance"]))
    level = confidence_level(confidence)
    text = (
        f"本次预测基于 {len(samples)} 个历史相似样本。"
        f"最相似样本的血压为 {closest['sbp']}/{closest['dbp']} mmHg，"
        f"向量距离为 {float(closest['distance']):.4f}。"
        f"相似样本平均距离 {avg_distance:.4f}，"
        f"收缩压标准差 {sbp_std:.1f} mmHg。"
        f"预测结果为 {sbp_pred}/{dbp_pred} mmHg。"
    )
    if confidence < UNRELIABLE_CONFIDENCE_THRESHOLD:
        text += " 预测结果不可靠，请重新上传信号。"
    elif confidence < LOW_CONFIDENCE_THRESHOLD:
        text += " 预测置信度较低，建议重新测量或选择其他样本。"
    if sbp_std > LARGE_SBP_STD:
        text += " 注意：相似样本血压差异较大，建议多次测量或咨询医生。"

    return text, {
        "sample_count": len(samples),
        "avg_distance": round(avg_distance, 4),
        "sbp_std": round(sbp_std, 2),
        "closest_sample": closest,
        "confidence": confidence,
        "confidence_level": level,
        "warning": confidence_warning(confidence, sbp_std),
    }


def build_explainability(samples: list[dict], weights: list[float] | None, workflow_trace: list[dict] | None) -> dict:      #前端可解释全量结构化数据
    weights = weights or calculate_sample_weights(samples)
    weighted_samples = []
    for index, sample in enumerate(samples):
        weight = float(weights[index]) if index < len(weights) else 0.0
        weighted_samples.append(
            {
                **sample,
                "rank": index + 1,
                "weight": round(weight, 6),
                "weight_percent": round(weight * 100, 1),
            }
        )
    return {
        "levels": ["L1_result", "L2_similar_samples", "L3_process"],
        "weighted_samples": weighted_samples,
        "workflow_trace": workflow_trace or [],
    }


def confidence_level(confidence: float) -> str:     #置信等级标签
    if confidence < UNRELIABLE_CONFIDENCE_THRESHOLD:
        return "unreliable"
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return "low"
    return "acceptable"

    
def confidence_warning(confidence: float, sbp_std: float) -> str | None:        #告警文案
    if confidence < UNRELIABLE_CONFIDENCE_THRESHOLD:
        return "预测结果不可靠，请重新上传信号"
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return "预测置信度较低，建议重新测量或选择其他样本"
    if sbp_std > LARGE_SBP_STD:
        return "相似样本血压差异较大，建议多次测量或咨询医生"
    return None
