from typing import Any

# 统一 API 返回格式工具函数

def success(data: Any = None, message: str = "ok") -> dict[str, Any]:       #success(要返回的数据, 提示文案)，生成统一格式的成功 JSON。
    return {"success": True, "message": message, "data": data}


def fail(message: str, code: int = 400, data: Any = None) -> dict[str, Any]:
    return {"success": False, "code": code, "message": message, "data": data}
