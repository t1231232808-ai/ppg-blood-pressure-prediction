import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.models.database import SessionLocal
from app.models.entities import SystemConfig


DESCRIPTIONS = {
    "top_k_default": "Milvus相似检索默认Top-K值",
    "confidence_threshold": "预测置信度阈值",
    "milvus_nprobe": "Milvus IVF索引nprobe参数",
    "snr_threshold": "PPG信号质量评估SNR阈值dB",
}


def main() -> None:
    with SessionLocal() as db:
        for key, description in DESCRIPTIONS.items():
            config = db.scalar(select(SystemConfig).where(SystemConfig.config_key == key))
            if config:
                config.description = description
        db.commit()
    print("Config descriptions fixed.")


if __name__ == "__main__":
    main()
