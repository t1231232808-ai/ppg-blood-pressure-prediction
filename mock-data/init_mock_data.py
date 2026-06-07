#!/usr/bin/env python3
"""
Milvus 模拟数据初始化脚本
生成 500 条模拟 PPG 数据，编码为 128 维向量后插入 Milvus
"""

import numpy as np
import sys
import os

# 添加项目路径，以便导入后端服务模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.feature_extraction import extract_features, fit_pca_model, encode_vector
from app.services.milvus_service import init_milvus, insert_vectors


def generate_ppg_signal(sbp, dbp, length=1250, fs=125):
    """
    根据目标血压生成模拟 PPG 信号
    
    思路：
    - 基础波形 = 正弦波（模拟心跳）
    - 血压越高 → 波形幅值越大、波峰越尖锐
    - 添加高斯噪声模拟真实信号的随机波动
    
    Args:
        sbp: 收缩压，影响波形幅值
        dbp: 舒张压，影响波形基线
        length: 信号长度（采样点数）
        fs: 采样率
    
    Returns:
        numpy array, shape=(length,)
    """
    t = np.arange(length) / fs
    
    # 心率：根据血压微调（高血压心率略高）
    heart_rate = 60 + (sbp - 120) * 0.2  # bpm
    freq = heart_rate / 60.0  # Hz
    
    # 基础正弦波（心跳）
    base = np.sin(2 * np.pi * freq * t)
    
    # 谐波成分（让波形更像真实 PPG）
    harmonic = 0.3 * np.sin(2 * np.pi * 2 * freq * t)
    
    # 幅值与收缩压正相关
    amplitude = 0.3 + (sbp - 100) * 0.005
    
    # 基线与舒张压正相关
    baseline = 0.2 + (dbp - 60) * 0.008
    
    # 合成信号
    signal = baseline + amplitude * (base + harmonic)
    
    # 添加高斯噪声（SNR 约 15~25dB）
    noise_std = amplitude * 0.05
    noise = np.random.normal(0, noise_std, length)
    signal = signal + noise
    
    # 归一化到 [0, 1]
    signal = (signal - signal.min()) / (signal.max() - signal.min())
    
    return signal


def generate_mock_dataset(n_samples=500):
    """
    生成模拟数据集
    
    血压分布：
    - 正常血压（SBP 100~120）：40%
    - 偏高血压（SBP 120~140）：35%
    - 高血压（SBP 140~160）：20%
    - 低血压（SBP 90~100）：5%
    """
    data = []
    
    for i in range(n_samples):
        # 随机选择血压类别
        category = np.random.choice(
            ['normal', 'elevated', 'hypertension', 'hypotension'],
            p=[0.40, 0.35, 0.20, 0.05]
        )
        
        if category == 'normal':
            sbp = np.random.randint(100, 121)
            dbp = np.random.randint(65, 81)
        elif category == 'elevated':
            sbp = np.random.randint(120, 141)
            dbp = np.random.randint(75, 91)
        elif category == 'hypertension':
            sbp = np.random.randint(140, 161)
            dbp = np.random.randint(85, 101)
        else:  # hypotension
            sbp = np.random.randint(90, 101)
            dbp = np.random.randint(55, 66)
        
        # 生成 PPG 信号
        signal = generate_ppg_signal(sbp, dbp)
        
        # 提取特征并编码
        features = extract_features(signal)
        
        data.append({
            'features': features,
            'sbp': sbp,
            'dbp': dbp,
            'source': 'mock',
            'mock_id': f"generated_{i + 1:03d}",
        })
    
    return data


def main():
    print("=" * 50)
    print("Milvus 模拟数据初始化")
    print("=" * 50)
    
    # 步骤 1：生成模拟数据
    print("\n[1/4] 生成模拟数据集...")
    mock_data = generate_mock_dataset(n_samples=500)
    print(f"      生成完成：{len(mock_data)} 条样本")
    
    # 步骤 2：拟合 PCA 模型
    print("\n[2/4] 拟合 PCA 降维模型...")
    feature_matrix = np.array([d['features'] for d in mock_data])
    pca_model = fit_pca_model(feature_matrix)
    print(f"      PCA 模型已保存到 app/static/pca_model.pkl")
    
    # 步骤 3：编码为 128 维向量
    print("\n[3/4] 编码特征向量...")
    vectors = []
    sbps = []
    dbps = []
    sources = []
    mock_ids = []
    
    for item in mock_data:
        vector = encode_vector(item['features'], pca_model)
        vectors.append(vector.tolist())
        sbps.append(item['sbp'])
        dbps.append(item['dbp'])
        sources.append(item['source'])
        mock_ids.append(item['mock_id'])
    
    print(f"      编码完成：{len(vectors)} 个 128 维向量")
    
    # 步骤 4：初始化 Milvus 并插入数据
    print("\n[4/4] 初始化 Milvus 并插入数据...")
    collection = init_milvus()
    
    # 清空已有数据（如果存在）
    if collection.num_entities > 0:
        print(f"      检测到已有数据 {collection.num_entities} 条，正在清空...")
        collection.drop()
        collection = init_milvus()
    
    primary_keys = insert_vectors(vectors, sbps, dbps, sources, mock_ids=mock_ids)
    print(f"      插入完成：{len(primary_keys)} 条向量")
    print(f"      集合总行数：{collection.num_entities}")
    
    print("\n" + "=" * 50)
    print("初始化完成！")
    print("=" * 50)


if __name__ == '__main__':
    main()
