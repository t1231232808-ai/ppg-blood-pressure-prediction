from sqlalchemy import BigInteger, DateTime, DECIMAL, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base
# 数据库表结构定义文件，4 个 Class 对应 MySQL 里 4 张物理数据表，采用 Mapped + mapped_column 新语法（SQLAlchemy2.0 声明式 ORM），
# 和前面db.py的Base基类关联，执行Base.metadata.create_all(engine)自动生成数据表。

class User(Base):
    # 用户表：保存账号、邮箱、密码哈希、角色和状态。
    __tablename__ = "users" # 对应mysql真实表名：users
    # 主键ID 大整型自增
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 用户名：50字符，唯一不可重复，非空
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # 邮箱：100字符，唯一非空
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # 密码哈希（不存明文密码），255字符非空
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 角色枚举：只能填user/admin，默认普通user
    role: Mapped[str] = mapped_column(Enum("user","admin",name="user_role"), nullable=False, default="user")
    # 状态：int，默认1（1启用/0禁用）
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 创建时间：数据库默认自动填当前时间
    created_at = mapped_column(DateTime, nullable=False, server_default=func.now())
    # 更新时间：新增时默认now，修改记录自动刷新为当前时间
    updated_at = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # 一对多关联：一个用户 → 多条预测记录
    records: Mapped[list["PredictionRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    # 建立索引：加速用户名、邮箱查询
    __table_args__ = (Index("idx_username", "username"), Index("idx_email", "email"))


class PredictionRecord(Base):
    # 预测记录表：每次预测的血压结果、置信度、解释都会存在这里。
    __tablename__ = "prediction_records"
    # 外键user_id：关联users.id，父表用户删除→本条记录级联删除(ON DELETE CASCADE)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sbp_predicted: Mapped[int] = mapped_column(Integer, nullable=False)
    dbp_predicted: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence = mapped_column(DECIMAL(3, 2), nullable=False)
    similar_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_distance = mapped_column(DECIMAL(8, 4), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, nullable=False, server_default=func.now())
    # 多对一：多条预测记录归属同一个用户
    user: Mapped[User] = relationship(back_populates="records")
    # 一对多：一条预测记录对应多条原始PPG波形数据
    raw_data: Mapped["PpgRawData"] = relationship(back_populates="record", cascade="all, delete-orphan")
    # 索引：按用户ID、创建时间快速筛选历史记录
    __table_args__ = (Index("idx_user_id", "user_id"), Index("idx_created_at", "created_at"))


class PpgRawData(Base):
    # 原始 PPG 数据表：把每次预测用到的波形单独存起来。1 个用户 → N 条预测记录 → 每条预测记录附带 N 条原始 PPG 波形
    __tablename__ = "ppg_raw_data"
    # 外键绑定预测记录ID，一条预测记录对应多条波形，unique保证一条波形只归属一条记录
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("prediction_records.id", ondelete="CASCADE"), unique=True)
    signal_json: Mapped[str] = mapped_column(Text, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=125)
    duration = mapped_column(DECIMAL(4, 1), nullable=False, default=10.0)
    created_at = mapped_column(DateTime, nullable=False, server_default=func.now())
    # 多对一：波形归属某一条预测记录
    record: Mapped[PredictionRecord] = relationship(back_populates="raw_data")


class SystemConfig(Base):
    # 系统配置表：一些可以后台调整的参数会放这里，比如阈值、检索数量等。
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    config_value: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_config_key", "config_key"),)
