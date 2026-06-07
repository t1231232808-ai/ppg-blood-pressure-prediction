from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
import pandas as pd
from scipy import signal

from app.utils.exceptions import PPGQualityError, PPGValidationError


SAMPLE_RATE = 125               # 标准采样率：125Hz
EXPECTED_INTERVAL = 1.0 / SAMPLE_RATE # 采样点理论间隔 1/125 s
MIN_POINTS = 1000               # CSV最少采样点数
MAX_POINTS = 1500               # CSV最多采样点数
TARGET_POINTS = 1250            # 预处理后统一固定波形长度1250点
LOWCUT_HZ = 0.5                 # 带通滤波下限0.5Hz
HIGHCUT_HZ = 8.0                # 带通滤波上限8Hz
SIGNAL_BAND_MAX_HZ = 4.0        # 有效生理信号最高频率4Hz（用于SNR信噪比计算）
FILTER_ORDER = 4                # Butterworth滤波器阶数


@dataclass
class PreprocessResult:
    signal: list[float]       # 最终标准化PPG波形数组
    snr: float                # 信噪比（dB，信号质量核心指标）
    sample_rate: int = SAMPLE_RATE
    duration: float = 10.0    # 波形总时长(s)
    points: int = TARGET_POINTS
    quality: dict = field(default_factory=dict) # 全量质控信息


def read_ppg_csv(file_bytes: bytes) -> pd.DataFrame:
    # 校验 CSV 格式、列名、采样时序、数据合法性，不满足直接抛PPGValidationError(400)
    try:
        df = pd.read_csv(BytesIO(file_bytes))
    except Exception as exc:
        raise PPGValidationError("CSV文件读取失败，请检查文件格式") from exc

    required = {"timestamp", "ppg_value"}
    if not required.issubset(df.columns):
        missing = "、".join(sorted(required - set(df.columns)))
        raise PPGValidationError(f"CSV缺少必要列: {missing}")

    df = df[["timestamp", "ppg_value"]].copy()
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["ppg_value"] = pd.to_numeric(df["ppg_value"], errors="coerce")
    if df[["timestamp", "ppg_value"]].isna().any().any():
        raise PPGValidationError("timestamp 和 ppg_value 必须为数值型，且不能为空")

    if len(df) < MIN_POINTS or len(df) > MAX_POINTS:
        raise PPGValidationError(f"数据行数应在{MIN_POINTS}~{MAX_POINTS}之间，当前{len(df)}")

    timestamps = df["timestamp"].to_numpy(dtype=np.float64)
    if timestamps[0] < -0.001 or abs(timestamps[0]) > 0.05:
        raise PPGValidationError("timestamp 应从 0 秒附近开始")
    if np.any(np.diff(timestamps) <= 0):
        raise PPGValidationError("timestamp 必须严格递增")

    intervals = np.diff(timestamps)
    if not np.allclose(intervals, EXPECTED_INTERVAL, atol=0.001):
        # 项目要求 125Hz 采样，所以相邻时间点应该基本固定。
        raise PPGValidationError("时间戳不连续，采样率应为125Hz")

    return df


def calculate_snr(values: np.ndarray, sample_rate: int = SAMPLE_RATE) -> float:
    # 算信噪比。简单说，就是看有效 PPG 信号比噪声强多少。
    centered = np.asarray(values, dtype=np.float64) - float(np.mean(values))
    freqs = np.fft.rfftfreq(centered.size, d=1.0 / sample_rate)
    fft_values = np.abs(np.fft.rfft(centered))

    signal_mask = (freqs >= LOWCUT_HZ) & (freqs <= SIGNAL_BAND_MAX_HZ)
    noise_mask = (freqs > HIGHCUT_HZ) | ((freqs > 0) & (freqs < LOWCUT_HZ))
    signal_power = float(np.sum(fft_values[signal_mask] ** 2) / centered.size)
    noise_power = float(np.sum(fft_values[noise_mask] ** 2) / centered.size)
    if noise_power < 1e-10:
        return 999.0
    if signal_power < 1e-10:
        return -999.0
    return float(10 * np.log10(signal_power / noise_power))


def bandpass_filter(
    values: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    lowcut: float = LOWCUT_HZ,
    highcut: float = HIGHCUT_HZ,
    order: int = FILTER_ORDER,
) -> np.ndarray:
    # 带通滤波：只保留 PPG 里比较有用的频段，把太慢或太快的干扰压掉。
    nyquist = sample_rate / 2
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(order, [low, high], btype="band")
    return signal.filtfilt(b, a, values)


def normalize_signal(values: np.ndarray) -> np.ndarray:
    # 把波形压到 0~1 之间，这样后面的特征提取更稳定。
    min_value = float(np.min(values))
    max_value = float(np.max(values))
    if abs(max_value - min_value) < 1e-10:
        raise PPGValidationError("PPG信号幅值差异过小，无法归一化")
    return (values - min_value) / (max_value - min_value)


def preprocess_values(values: np.ndarray, snr_threshold: float = 10.0) -> PreprocessResult:
    # 这里是真正的预处理主流程：检查数据 -> 看信号质量 -> 滤波 -> 重采样 -> 归一化。
    values = np.asarray(values, dtype=np.float64)
    if values.size < MIN_POINTS or values.size > MAX_POINTS:
        raise PPGValidationError(f"数据行数应在{MIN_POINTS}~{MAX_POINTS}之间，当前{values.size}")
    if not np.isfinite(values).all():
        raise PPGValidationError("PPG信号包含无效数值")

    duration = round(values.size / SAMPLE_RATE, 2)
    snr = calculate_snr(values)
    if snr < snr_threshold:
        # 信号太差时直接拒绝预测，不然算出来的血压没有参考意义。
        raise PPGQualityError(f"信号质量过低，SNR={snr:.2f} dB，要求≥{snr_threshold:.0f}dB")

    detrended = signal.detrend(values)
    filtered = bandpass_filter(detrended)
    resampled = signal.resample(filtered, TARGET_POINTS)
    normalized = normalize_signal(resampled)
    rounded_snr = round(snr, 2)
    return PreprocessResult(
        signal=normalized.astype(float).tolist(),
        snr=rounded_snr,
        duration=duration,
        quality={
            "snr": rounded_snr,
            "snr_threshold": snr_threshold,
            "sample_rate": SAMPLE_RATE,
            "duration": duration,
            "points": TARGET_POINTS,
            "original_points": int(values.size),
            "filter": {
                "type": "butterworth_bandpass",
                "order": FILTER_ORDER,
                "lowcut_hz": LOWCUT_HZ,
                "highcut_hz": HIGHCUT_HZ,
                "zero_phase": True,
            },
            "normalization": "min_max_0_1",
            "denoise_strategy": "adaptive_bandpass",
            "status": "accepted",
        },
    )


def preprocess_csv(file_bytes: bytes, snr_threshold: float = 10.0) -> PreprocessResult:
    # 给路由层用的入口：传 CSV 文件内容进来，返回处理好的 PPG 波形。
    df = read_ppg_csv(file_bytes)
    return preprocess_values(df["ppg_value"].to_numpy(dtype=np.float64), snr_threshold=snr_threshold)
