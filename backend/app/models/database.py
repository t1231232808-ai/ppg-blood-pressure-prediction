from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):        #定义 ORM 基类 Base
    pass


settings = get_settings()
# 1. 创建数据库引擎+连接池
# 从配置类拿到完整 mysql 连接串/取用连接前自动 ping 数据库，自动剔除失效、断线的数据库连接/连接池回收闲置连接，单位秒 = 3600s=1 小时
engine = create_engine(settings.mysql_url, pool_pre_ping=True, pool_recycle=3600)     
# 2. 创建会话工厂
# 会话绑定到上面创建的数据库引擎/关闭自动提交，必须手动 db.commit () 才会落库/关闭自动刷新，修改数据不会自动同步数据库
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)     


# 生成器实现数据库会话的自动创建、自动关闭
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()     # 创建一个数据库会话
    try:
        yield db     # 把 db 会话产出给接口函数使用
    finally:
        db.close()      #接口请求结束后，无论成功 / 报错，最终都会关闭会话归还连接池
