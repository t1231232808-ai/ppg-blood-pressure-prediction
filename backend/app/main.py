import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import admin, auth, health, prediction, records
from app.utils.response import fail


settings = get_settings()
logger = logging.getLogger(__name__)

# 这里就是创建整个后端应用，名字和版本主要是给接口文档看的。
app = FastAPI(title="PPG Blood Pressure Prediction API", version="0.1.0")

# 这里处理跨域问题。简单说，就是允许前端页面来调用这个后端接口。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 下面是在把不同模块的接口挂到后端上。
# 比如登录相关的接口会变成 /api/v1/auth/xxx，预测相关的接口会变成 /api/v1/prediction/xxx。
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(prediction.router, prefix="/api/v1/prediction", tags=["prediction"])
app.include_router(records.router, prefix="/api/v1/records", tags=["records"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # 如果代码里有没预料到的错误，就会走到这里。
    # 后端会把错误记到日志里，但返回给前端的是比较友好的“服务器内部错误”。
    logger.exception("Unhandled exception: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content=fail("服务器内部错误", code=500))
