import json
from pathlib import Path

import numpy as np
import pandas as pd


MOCK_SAMPLES = [
    ("mock_001", "正常血压样本A", "模拟正常血压波形，SBP~120", 120, 78, 1.20),
    ("mock_002", "正常血压样本B", "模拟正常血压波形，SBP~115", 115, 75, 1.12),
    ("mock_003", "偏高血压样本A", "模拟偏高血压波形，SBP~135", 135, 84, 1.28),
    ("mock_004", "高血压样本A", "模拟高血压波形，SBP~145", 145, 90, 1.34),
    ("mock_005", "低血压样本A", "模拟低血压波形，SBP~100", 100, 64, 1.05),
    ("mock_006", "正常血压样本C", "模拟正常血压波形，SBP~118", 118, 76, 1.18),
    ("mock_007", "正常血压样本D", "模拟正常血压波形，SBP~122", 122, 79, 1.22),
    ("mock_008", "偏高血压样本B", "模拟偏高血压波形，SBP~132", 132, 82, 1.26),
    ("mock_009", "偏高血压样本C", "模拟偏高血压波形，SBP~138", 138, 86, 1.30),
    ("mock_010", "高血压样本B", "模拟高血压波形，SBP~150", 150, 92, 1.38),
    ("mock_011", "低血压样本B", "模拟低血压波形，SBP~96", 96, 60, 1.02),
    ("mock_012", "正常血压样本E", "模拟正常血压波形，SBP~124", 124, 78, 1.24),
    ("mock_013", "正常血压样本F", "模拟正常血压波形，SBP~110", 110, 70, 1.10),
    ("mock_014", "偏高血压样本D", "模拟偏高血压波形，SBP~130", 130, 81, 1.25),
    ("mock_015", "高血压样本C", "模拟高血压波形，SBP~155", 155, 94, 1.42),
    ("mock_016", "低血压样本C", "模拟低血压波形，SBP~102", 102, 66, 1.06),
    ("mock_017", "正常血压样本G", "模拟正常血压波形，SBP~116", 116, 74, 1.14),
    ("mock_018", "偏高血压样本E", "模拟偏高血压波形，SBP~140", 140, 88, 1.32),
    ("mock_019", "高血压样本D", "模拟高血压波形，SBP~160", 160, 96, 1.45),
    ("mock_020", "正常血压样本H", "模拟正常血压波形，SBP~125", 125, 79, 1.23),
]


def generate_ppg_csv(
    output: Path,
    sample_rate: int = 125,
    duration: int = 10,
    seed: int = 20260509,
    heart_rate_hz: float = 1.2,
    amplitude_scale: float = 1.0,
) -> None:
    rng = np.random.default_rng(seed)
    point_count = sample_rate * duration
    timestamp = np.arange(point_count, dtype=np.float64) / sample_rate
    ppg_value = (
        amplitude_scale * 0.65 * np.sin(2 * np.pi * heart_rate_hz * timestamp)
        + amplitude_scale * 0.22 * np.sin(2 * np.pi * 2 * heart_rate_hz * timestamp + 0.5)
        + 0.08 * np.sin(2 * np.pi * 0.2 * timestamp)
        + rng.normal(0, 0.03, size=point_count)
    )
    df = pd.DataFrame({"timestamp": timestamp, "ppg_value": ppg_value})
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)


def generate_predefined_samples(base_dir: Path) -> None:
    sample_dir = base_dir / "predefined"
    manifest = []
    for index, (mock_id, name, description, sbp, dbp, heart_rate_hz) in enumerate(MOCK_SAMPLES, start=1):
        filename = f"{mock_id}.csv"
        generate_ppg_csv(
            sample_dir / filename,
            seed=20260510 + index,
            heart_rate_hz=heart_rate_hz,
            amplitude_scale=0.92 + index * 0.008,
        )
        manifest.append(
            {
                "mock_id": mock_id,
                "name": name,
                "description": description,
                "sbp": sbp,
                "dbp": dbp,
                "filename": filename,
            }
        )
    (sample_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    generate_ppg_csv(root / "sample_ppg.csv")
    generate_predefined_samples(root)
    print("Generated mock-data/sample_ppg.csv and mock-data/predefined/*.csv")
