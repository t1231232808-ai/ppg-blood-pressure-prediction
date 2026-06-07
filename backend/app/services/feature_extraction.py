from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy import signal as scipy_signal
from scipy import stats
from sklearn.decomposition import PCA


VECTOR_DIM = 128    # 最终入库Milvus的向量固定维度128
FEATURE_DIM = 24    # 手工提取特征固定24维
SAMPLE_RATE = 125   # 采样率125Hz
PCA_MODEL_PATH = Path(__file__).resolve().parents[1] / "static" / "pca_model.pkl"   # PCA预训练模型文件路径


def extract_features(ppg_signal: list[float] | np.ndarray, fs: int = SAMPLE_RATE) -> np.ndarray:
    # 把一段 PPG 波形变成一组数字特征，比如均值、波峰数量、频率特征等。
    values = np.asarray(ppg_signal, dtype=np.float64)   #数据校验：必须一维非空数组，否则抛异常。
    if values.ndim != 1 or values.size == 0:
        raise ValueError("PPG信号必须是一维非空数组")

    centered = values - np.mean(values)     # 去均值
    fft_values = np.abs(np.fft.rfft(centered))
    freqs = np.fft.rfftfreq(values.size, 1 / fs)      #FFT 傅里叶变换：得到频谱、功率谱 PSD，用于频域特征
    psd = fft_values**2
    total_energy = float(np.sum(psd)) + 1e-12
    duration = values.size / fs
    non_dc_fft = fft_values.copy()
    if non_dc_fft.size:
        non_dc_fft[0] = 0
    dominant_index = int(np.argmax(non_dc_fft)) if non_dc_fft.size else 0

    peaks, properties = scipy_signal.find_peaks(values, distance=fs // 3, prominence=0.1, width=1)  #峰值检测
    # 这里拼出来的是 24 个特征，后面会再转成固定长度的 128 维向量。
    features = [
        # 均值、标准差、最大、最小、峰峰值、偏度、峰度、过零率、波形面积、
        # 总能量、主频、主频幅值、谱熵、高低频能量占比、谱重心、脉搏峰数量、
        # 峰间隔均值 / 方差、峰高均值 / 方差、上升时间均值、下降时间均值、脉宽均值
        float(np.mean(values)),
        float(np.std(values)),
        float(np.max(values)),
        float(np.min(values)),
        float(np.ptp(values)),
        float(stats.skew(values)),
        float(stats.kurtosis(values)),
        _zero_crossing_rate(centered),
        # 下面几个用“单位时间/单位点数”的写法，避免采样时长不同导致特征天然变大。
        float(np.sum(values) / duration),
        float(np.sum(values**2) / duration),
        float(freqs[dominant_index]) if freqs.size else 0.0,
        float(fft_values[dominant_index] / values.size) if fft_values.size else 0.0,
        _spectral_entropy(psd),
        _band_energy_ratio(freqs, psd, 2.0, 8.0, total_energy),
        _band_energy_ratio(freqs, psd, 0.5, 2.0, total_energy),
        float(np.sum(freqs * psd) / total_energy),
        float(len(peaks) / duration),
        *_morphology_features(values, peaks, properties, fs),
    ]
    #把运算产生的 NaN / 无穷值置 0，防止后续报错。
    return np.nan_to_num(np.asarray(features, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)


def load_pca_model(path: Path = PCA_MODEL_PATH) -> PCA | None:
    # 如果项目里有训练好的 PCA 模型，就加载它；没有的话就直接不用。
    if not path.exists():
        return None
    return joblib.load(path)


def fit_pca_model(feature_matrix: np.ndarray, path: Path = PCA_MODEL_PATH) -> PCA:
    # 用一批特征训练 PCA 模型。这个更多是初始化或重建模型时用。
    matrix = np.asarray(feature_matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] < 2:
        raise ValueError("PCA训练数据至少需要2条特征样本")
    n_components = min(VECTOR_DIM, matrix.shape[0], matrix.shape[1])
    pca = PCA(n_components=n_components)
    pca.fit(matrix)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pca, path)
    return pca


def encode_features(features: np.ndarray, pca_model: PCA | None = None) -> list[float]:
    # 把特征整理成 Milvus 需要的 128 维向量，并做归一化。
    values = np.asarray(features, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("特征向量必须是一维数组")

    transformed = _transform_with_pca(values, pca_model)
    vector = _pad_or_trim(transformed, VECTOR_DIM)
    norm = float(np.linalg.norm(vector))
    if norm > 1e-12:
        vector = vector / norm
    return vector.astype(np.float32).tolist()


def encode_vector(ppg_signal_or_features: list[float] | np.ndarray, pca_model: PCA | None = None) -> list[float]:
    # 对外最常用的入口：可以传原始波形，也可以直接传 24 维特征。
    values = np.asarray(ppg_signal_or_features, dtype=np.float64)
    features = values if values.size == FEATURE_DIM else extract_features(values)
    return encode_features(features, pca_model=pca_model)


def feature_names() -> list[str]:
    # 这些名字和 extract_features 里生成特征的顺序是一一对应的。
    return [
        "mean",
        "std",
        "max",
        "min",
        "peak_to_peak",
        "skewness",
        "kurtosis",
        "zero_crossing_rate",
        "waveform_area_rate",
        "energy_rate",
        "dominant_freq",
        "dominant_freq_mag_norm",
        "spectral_entropy",
        "hf_energy_ratio",
        "lf_energy_ratio",
        "spectral_centroid",
        "peak_rate",
        "peak_interval_mean",
        "peak_interval_std",
        "peak_height_mean",
        "peak_height_std",
        "rise_time_mean",
        "fall_time_mean",
        "pulse_width_mean",
    ]


def _zero_crossing_rate(values: np.ndarray) -> float:
    signs = np.sign(values)
    return float(np.sum(np.diff(signs) != 0) / values.size)


def _spectral_entropy(psd: np.ndarray) -> float:
    psd_norm = psd / (float(np.sum(psd)) + 1e-12)
    return float(-np.sum(psd_norm * np.log2(psd_norm + 1e-10)))


def _band_energy_ratio(freqs: np.ndarray, psd: np.ndarray, low: float, high: float, total_energy: float) -> float:
    mask = (freqs >= low) & (freqs <= high)
    return float(np.sum(psd[mask]) / total_energy)


def _morphology_features(values: np.ndarray, peaks: np.ndarray, properties: dict[str, Any], fs: int) -> list[float]:
    # 这里提取的是波形形态相关的特征，比如波峰间隔、上升时间、下降时间。
    if len(peaks) < 2:
        return [0.0] * 7

    peak_intervals = np.diff(peaks) / fs
    peak_heights = values[peaks]
    widths = properties.get("widths", np.array([0.0]))
    troughs = _find_troughs(values, peaks)
    rise_times = []
    fall_times = []

    for index, peak in enumerate(peaks):
        prev_trough = troughs[index] if index < len(troughs) else max(0, peak - fs // 2)
        next_start = peak + 1
        next_end = peaks[index + 1] if index < len(peaks) - 1 else len(values)
        next_trough = next_start + int(np.argmin(values[next_start:next_end])) if next_end > next_start else peak
        rise_times.append(max(0, peak - prev_trough) / fs)
        fall_times.append(max(0, next_trough - peak) / fs)

    return [
        float(np.mean(peak_intervals)),
        float(np.std(peak_intervals)),
        float(np.mean(peak_heights)),
        float(np.std(peak_heights)),
        float(np.mean(rise_times)),
        float(np.mean(fall_times)),
        float(np.mean(widths) / fs),
    ]


def _find_troughs(values: np.ndarray, peaks: np.ndarray) -> list[int]:
    troughs = []
    for index, peak in enumerate(peaks):
        start = peaks[index - 1] if index > 0 else 0
        if peak > start:
            troughs.append(start + int(np.argmin(values[start:peak])))
    return troughs


def _transform_with_pca(features: np.ndarray, pca_model: PCA | None = None) -> np.ndarray:
    # 如果有 PCA 模型，就用它做降维/变换；没有模型就保留原特征。
    model = pca_model or load_pca_model()
    if model is None:
        return features
    expected_dim = getattr(model, "n_features_in_", features.size)
    adjusted = _pad_or_trim(features, int(expected_dim))
    transformed = model.transform(adjusted.reshape(1, -1))[0]
    return np.asarray(transformed, dtype=np.float64)


def _pad_or_trim(values: np.ndarray, size: int) -> np.ndarray:
    # 长了就截断，短了就补 0，保证向量长度固定。
    output = np.zeros(size, dtype=np.float64)
    count = min(values.size, size)
    output[:count] = values[:count]
    return output
