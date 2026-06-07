from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

#API 请求入参校验 + 接口返回出参格式化


class UserCreate(BaseModel):        #用户注册接口 请求入参模型
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):     #用户登录接口 请求入参模型
    username: str
    password: str


class UserOut(BaseModel):       #查询用户 接口返回出参模型，数据库 ORM 对象 → 返回前端 JSON
    id: int
    username: str
    email: str
    role: str
    status: int
    created_at: datetime | None = None
    #1、支持从对象属性取值（ORM 对象本质是类实例，用.xxx 取字段）
    #2、只提取模型里声明的字段，自动屏蔽数据库多余字段、敏感字段
    model_config = {"from_attributes": True}        #让 Pydantic 模型可以直接接收 SQLAlchemy 数据库 ORM 对象，自动读取对象属性生成 JSON


class TokenOut(BaseModel):        #登录成功返回结果模型
    access_token: str       # JWT令牌字符串
    token_type: str = "bearer"      # 默认固定bearer（Authorization: Bearer xxx）
    user: UserOut       # 嵌套用户信息，复用上面UserOut结构


class PredictionOut(BaseModel):     #单次预测接口返回出参
    record_id: int | None = None        # 预测记录ID，可为空
    sbp: int | None                     # 预测收缩压
    dbp: int | None                     # 预测舒张压
    confidence: float | None            # 置信度
    explanation: str | None             # 解释文案
    blood_pressure_level: str | None = None         # 血压分级
    similar_samples: list[dict] = Field(default_factory=list)      # 相似波形列表，默认空列表
    #default_factory=list：每次实例化生成全新空列表，不用[]（[] 是全局静态列表会有复用 bug）


class MockPredictionRequest(BaseModel):         #模拟预测接口入参
    #pattern=正则：前端传的 mock_id 必须匹配mock_01 / mock_020这类格式，否则校验报错。
    mock_id: str = Field(pattern=r"^mock_(00[1-9]|01[0-9]|020)$")


class RecordOut(BaseModel):     #历史预测记录查询出参
    # 查询prediction_records历史记录的返回模型，和数据库PredictionRecord字段对应
    id: int
    filename: str
    sbp_predicted: int
    dbp_predicted: int
    confidence: Decimal   #Decimal：对应数据库DECIMAL定点小数，防止浮点精度丢失。
    similar_count: int
    avg_distance: Decimal | None
    explanation: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConfigOut(BaseModel):     #系统配置查询出参
    config_key: str
    config_value: str
    description: str | None

    model_config = {"from_attributes": True}


class ConfigUpdate(BaseModel):          #修改系统配置入参模型
    config_value: str | None = None
    value: str | None = None
