import random

import numpy as np

from app.services.feature_extraction import encode_vector, extract_features, fit_pca_model
from app.services.milvus_service import init_milvus, insert_vectors, milvus_service
from app.services.mock_data_service import list_mock_samples, read_mock_csv
from app.services.ppg_preprocess import TARGET_POINTS, normalize_signal, preprocess_csv

#Milvus 初始化 & 模拟数据集生成全代码详解
#整体用途：管理员接口 /milvus/initialize 底层函数，一键初始化向量库：
# 【本地预置真实 mock 波形 + 代码随机生成仿真 PPG 波形】→ 合并数据集训练 PCA 模型 → 全量向量灌入 Milvus，搭建相似检索样本库

def initialize_feature_store(generated_count: int = 500) -> dict:   # 入口总函数（初始化 Milvus 全流程）
    predefined_dataset = _load_predefined_mock_dataset()    # 加载项目本地已存CSV真实mock样本
    generated_dataset = _generate_mock_dataset(generated_count) # 随机生成N条仿真PPG数据
    dataset = predefined_dataset + generated_dataset        #预置数据集 + 生成数据集

    feature_matrix = np.vstack([item["features"] for item in dataset])      #组装特征矩阵训练 PCA
    pca_model = fit_pca_model(feature_matrix)
    vectors = [encode_vector(item["features"], pca_model=pca_model) for item in dataset]    #批量生成 128 维 Milvus 向量

    milvus_service.drop_collection() # 删除旧集合
    collection = init_milvus()       # 新建集合+创建IVF索引
    primary_keys = insert_vectors(
        vectors,
        [item["sbp"] for item in dataset],
        [item["dbp"] for item in dataset],
        [item["source"] for item in dataset],
        mock_ids=[item["mock_id"] for item in dataset],
    )
    collection.flush() # 数据落地磁盘
    collection.load()  # 加载进内存，立刻可用检索

    return {        #返回初始化统计信息
        "collection": collection.name,      #集合名
        "inserted": len(primary_keys),      #入库总数
        "row_count": collection.num_entities,
        "predefined_count": len(predefined_dataset),       #本地预置样本数量
        "generated_count": len(generated_dataset),         #随机生成样本数量
    }


def _load_predefined_mock_dataset() -> list[dict]:          #加载本地预置 mock 数据
    dataset = []
    for item in list_mock_samples():
        _filename, content = read_mock_csv(item["mock_id"])
        processed = preprocess_csv(content, snr_threshold=0)
        dataset.append(
            {
                "features": extract_features(processed.signal),
                "sbp": int(item["sbp"]),
                "dbp": int(item["dbp"]),
                "source": "mock",
                "mock_id": item["mock_id"],
            }
        )
    return dataset


def _generate_mock_dataset(n_samples: int) -> list[dict]:       #批量随机生成仿真 PPG 数据集
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

        ppg_signal = _generate_ppg_signal(sbp, dbp, seed=index)
        dataset.append(
            {
                "features": extract_features(ppg_signal),
                "sbp": sbp,
                "dbp": dbp,
                "source": "mock",
                "mock_id": f"generated_{index + 1:03d}",
            }
        )
    return dataset


def _generate_ppg_signal(sbp: int, dbp: int, seed: int, length: int = TARGET_POINTS, fs: int = 125) -> np.ndarray:      #数学公式合成 PPG 脉搏波形
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
