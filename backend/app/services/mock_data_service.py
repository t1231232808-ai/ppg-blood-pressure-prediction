import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from app.services.ppg_preprocess import preprocess_csv


PROJECT_ROOT = Path(__file__).resolve().parents[3]      #获取当前文件往上 3 层目录 = 项目根目录，用来拼接静态文件路径
MOCK_DATA_DIR = PROJECT_ROOT / "mock-data" / "predefined"   #模拟 CSV 文件存放目录 项目根目录/mock-data/predefined/
MANIFEST_PATH = MOCK_DATA_DIR / "manifest.json"     #记录所有 mock 样例信息：mock_id、名称、描述、参考sbp/dbp血压值


@lru_cache(maxsize=1)   #函数缓存装饰器
def list_mock_samples() -> list[dict]:  #读取全部模拟样例清单（前端下拉选项数据源）
    if not MANIFEST_PATH.exists():
        raise HTTPException(status_code=500, detail="模拟数据清单不存在，请先生成 mock-data/predefined/manifest.json")
    try:
        samples = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="模拟数据清单格式错误") from exc
    return [
        {
            "mock_id": item["mock_id"],
            "name": item["name"],
            "description": item["description"],
            "sbp": item["sbp"],
            "dbp": item["dbp"],
        }
        for item in samples
    ]


def read_mock_csv(mock_id: str) -> tuple[str, bytes]:   #根据 mock_id 读取对应 CSV 文件
    sample = next((item for item in list_mock_samples() if item["mock_id"] == mock_id), None)
    if sample is None:
        raise HTTPException(status_code=404, detail="模拟数据不存在")
    filename = f"{mock_id}.csv"
    path = MOCK_DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"模拟数据文件缺失: {filename}")
    return filename, path.read_bytes()


def read_mock_signal(mock_id: str) -> list[float]:      #直接返回预处理后的 PPG 波形数组
    filename, content = read_mock_csv(mock_id)
    try:
        return preprocess_csv(content, snr_threshold=0).signal
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模拟数据文件读取失败: {filename}") from exc
