import random
from pathlib import Path
import sys
import os

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.feature_extraction import encode_vector, extract_features, fit_pca_model
from app.services.milvus_service import init_milvus, insert_vectors, milvus_service
from app.services.mock_data_service import list_mock_samples, read_mock_csv
from app.services.ppg_preprocess import TARGET_POINTS, normalize_signal
from app.services.ppg_preprocess import preprocess_csv


def generate_ppg_signal(sbp: int, dbp: int, seed: int, length: int = TARGET_POINTS, fs: int = 125) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(length) / fs
    heart_rate_hz = (62 + (sbp - 120) * 0.18 + rng.normal(0, 3)) / 60
    amplitude = 0.45 + (sbp - 100) * 0.004
    baseline = 0.15 + (dbp - 60) * 0.004
    pulse = (
        np.sin(2 * np.pi * heart_rate_hz * t)
        + 0.32 * np.sin(2 * np.pi * 2 * heart_rate_hz * t + 0.45)
        + 0.12 * np.sin(2 * np.pi * 3 * heart_rate_hz * t + 1.1)
    )
    drift = 0.05 * np.sin(2 * np.pi * 0.2 * t)
    noise = rng.normal(0, 0.025 + max(sbp - 120, 0) * 0.0003, length)
    return normalize_signal(baseline + amplitude * pulse + drift + noise)


def generate_mock_dataset(n_samples: int = 500) -> list[dict]:
    rng = random.Random(20260510)
    dataset = []
    categories = ["normal", "elevated", "hypertension", "hypotension"]
    weights = [0.40, 0.35, 0.20, 0.05]
    for index in range(n_samples):
        category = rng.choices(categories, weights=weights, k=1)[0]
        if category == "normal":
            sbp = rng.randint(100, 119)
            dbp = rng.randint(65, 79)
        elif category == "elevated":
            sbp = rng.randint(120, 139)
            dbp = rng.randint(75, 89)
        elif category == "hypertension":
            sbp = rng.randint(140, 160)
            dbp = rng.randint(85, 100)
        else:
            sbp = rng.randint(90, 99)
            dbp = rng.randint(55, 65)
        ppg_signal = generate_ppg_signal(sbp, dbp, seed=index)
        dataset.append(
            {
                "signal": ppg_signal,
                "features": extract_features(ppg_signal),
                "sbp": sbp,
                "dbp": dbp,
                "source": "mock",
                "mock_id": f"generated_{index + 1:03d}",
            }
        )
    return dataset


def load_predefined_mock_dataset() -> list[dict]:
    dataset = []
    for item in list_mock_samples():
        _filename, content = read_mock_csv(item["mock_id"])
        processed = preprocess_csv(content, snr_threshold=0)
        dataset.append(
            {
                "signal": processed.signal,
                "features": extract_features(processed.signal),
                "sbp": int(item["sbp"]),
                "dbp": int(item["dbp"]),
                "source": "mock",
                "mock_id": item["mock_id"],
            }
        )
    return dataset


def main() -> None:
    os.environ.setdefault("MILVUS_HOST", "127.0.0.1")
    os.environ.setdefault("MILVUS_PORT", "19530")

    print("[1/4] 生成模拟 PPG 数据...")
    dataset = load_predefined_mock_dataset() + generate_mock_dataset(500)

    print("[2/4] 拟合 PCA 模型...")
    feature_matrix = np.vstack([item["features"] for item in dataset])
    pca_model = fit_pca_model(feature_matrix)

    print("[3/4] 编码 128 维向量...")
    vectors = [encode_vector(item["features"], pca_model=pca_model) for item in dataset]
    sbps = [item["sbp"] for item in dataset]
    dbps = [item["dbp"] for item in dataset]
    sources = [item["source"] for item in dataset]
    mock_ids = [item["mock_id"] for item in dataset]

    print("[4/4] 初始化 Milvus 集合并导入数据...")
    milvus_service.drop_collection()
    collection = init_milvus()
    primary_keys = insert_vectors(vectors, sbps, dbps, sources, mock_ids=mock_ids)
    collection.flush()
    collection.load()
    print(f"导入完成：{len(primary_keys)} 条向量，集合：{collection.name}，Row count: {collection.num_entities}")


if __name__ == "__main__":
    main()
