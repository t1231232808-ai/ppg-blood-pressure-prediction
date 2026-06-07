from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"         # 项目运行环境：开发环境(development)
    app_secret_key: str = "change-me-in-production"     # 后端加密密钥
    mysql_host: str = "localhost"    # 数据库IP
    mysql_port: int = 3306      # MySQL默认端口
    mysql_user: str = "bp_user"     # 数据库账号
    mysql_password: str = "bp_password"     # 数据库密码
    mysql_db: str = "bp_prediction"     # 要连接的数据库名
    redis_host: str = "localhost"       # Redis IP
    redis_port: int = 6379      # Redis默认端口
    redis_db: int = 0       # Redis第0号库
    milvus_host: str = "localhost"       # Milvus IP
    milvus_port: int = 19530        # Milvus默认端口
    milvus_collection: str = "ppg_vectors"      # Milvus里的向量集合名称
    top_k_default: int = 5          # 向量检索默认返回Top5个结果
    confidence_threshold: float = 0.6       # 置信度阈值，低于0.6的数据过滤丢弃
    frontend_url: str = "http://localhost:5173"      # 前端页面地址，后端跨域/跳转要用

    model_config = SettingsConfigDict(
        env_file=".env",        # 指定从项目根目录 .env 文件读取配置
        env_file_encoding="utf-8",      # env文件编码
        case_sensitive=False,       # 环境变量大小写不敏感（MYSQL_HOST和mysql_host等效）
    )

    @property       # 调用settings.mysql_url时自动拼接 SQLAlchemy 连接字符串，ORM 框架 (SQLAlchemy) 直接用这个字符串连接数据库
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


@lru_cache      #全局只实例化一次 Settings 对象（单例）
def get_settings() -> Settings:
    return Settings()
