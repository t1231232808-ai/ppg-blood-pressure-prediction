import time
from typing import Any

import numpy as np
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from app.config import get_settings
from app.services.config_service import get_milvus_nprobe
#MilvusService 向量库封装代码全解

VECTOR_DIM = 128         # 向量固定128维，和前面特征编码输出统一
INDEX_TYPE = "IVF_FLAT" # Milvus索引类型
METRIC_TYPE = "L2"      # 相似度距离：欧式距离L2
NLIST = 128             # IVF索引聚类中心数
DEFAULT_NPROBE = 16     # 查询检索遍历聚类数


class MilvusService:
    # 封装 Milvus 全生命周期：建集合 / 建索引 / 插入 / 检索 / 删库
    def __init__(self) -> None:
        self.settings = get_settings()  #读取配置milvus_host/milvus_port/milvus_collection，保存集合名
        self.collection_name = self.settings.milvus_collection
        self._connected = False     #_connected标记连接状态，避免重复建立连接

    def connect(self) -> None:
        # 建立 Milvus 连接。已经连过的话就不重复连。
        if self._connected:
            return
        connections.connect(alias="default", host=self.settings.milvus_host, port=str(self.settings.milvus_port))
        self._connected = True

    def ensure_collection(self) -> Collection:
        # 确保向量集合存在。没有就创建，有了就检查索引，然后加载到内存。
        self.connect()
        if utility.has_collection(self.collection_name):
            collection = Collection(self.collection_name)   #直接拿到 Collection，校验索引；
            self._ensure_index(collection)
        else:
            collection = Collection(name=self.collection_name, schema=self._schema())   #用_schema()创建新集合 → 自动调用_ensure_index()建索引
            self._ensure_index(collection)
        collection.load()   #把集合数据加载进内存，加速查询
        return collection

    def drop_collection(self) -> None:
        # 删除整张向量集合，仅初始化重建 Milvus 时管理员接口调用
        self.connect()
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)

    def search_similar(     #相似波形检索，参数：检索向量、top_k取前N个最相似、source筛选来源
        self,
        vector: list[float] | np.ndarray,
        top_k: int = 5,
        source: str | None = None,
        nprobe: int | None = None,
    ) -> list[dict[str, Any]]:
        # 用当前 PPG 向量去 Milvus 里找最相似的历史样本。
        query_vector = self._normalize_vector(vector)
        collection = self.ensure_collection()
        expr = f'source == "{source}"' if source else None  #可选过滤来源（只查用户上传 / 只查 mock 数据）
        results = collection.search(    #L2 距离检索，返回 top_k 近邻，指定返回字段：sbp/dbp/source/record_id 等
            data=[query_vector],
            anns_field="vector",
            param={"metric_type": METRIC_TYPE, "params": {"nprobe": nprobe or get_milvus_nprobe()}},
            limit=top_k,
            expr=expr,
            output_fields=["sbp", "dbp", "source", "record_id", "mock_id", "create_time"],
        )
        return self._parse_search_results(results)  #_parse_search_results：Milvus 原生结果 → 转为前端友好字典格式

    def insert_vectors(     #批量插入向量
        self,
        vectors: list[list[float]] | list[np.ndarray],
        sbps: list[int],
        dbps: list[int],
        sources: list[str] | None = None,
        record_ids: list[int] | None = None,
        mock_ids: list[str] | None = None,
        source: str = "mock",
    ) -> list[int]:
        # 把一批 PPG 特征向量和对应的血压值写进 Milvus。
        if not (len(vectors) == len(sbps) == len(dbps)):
            raise ValueError("vectors、sbps、dbps 长度必须一致")
        actual_sources = sources if sources is not None else [source] * len(vectors)
        if len(actual_sources) != len(vectors):
            raise ValueError("sources 长度必须与 vectors 一致")
        actual_record_ids = record_ids if record_ids is not None else [0] * len(vectors)
        actual_mock_ids = mock_ids if mock_ids is not None else [""] * len(vectors)
        if len(actual_record_ids) != len(vectors):
            raise ValueError("record_ids 长度必须与 vectors 一致")
        if len(actual_mock_ids) != len(vectors):
            raise ValueError("mock_ids 长度必须与 vectors 一致")

        collection = self.ensure_collection()
        now = int(time.time())
        entities = [        #组装 entities 结构化数据：向量 + 血压 + 来源 + 主键 + 创建时间戳
            [self._normalize_vector(item) for item in vectors],
            [int(item) for item in sbps],
            [int(item) for item in dbps],
            [str(item) for item in actual_sources],
            [int(item or 0) for item in actual_record_ids],
            [str(item or "") for item in actual_mock_ids],
            [now] * len(vectors),
        ]
        result = collection.insert(entities)    #批量写入 Milvus、flush()落地磁盘
        collection.flush()
        return [int(item) for item in result.primary_keys]      #返回新增主键列表

    def _schema(self) -> CollectionSchema:
        # 定义 Milvus 集合里有哪些字段。vector 是用来相似检索的核心字段。
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM),
            FieldSchema(name="sbp", dtype=DataType.INT64),
            FieldSchema(name="dbp", dtype=DataType.INT64),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="record_id", dtype=DataType.INT64),
            FieldSchema(name="mock_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="create_time", dtype=DataType.INT64),
        ]
        return CollectionSchema(fields, description="PPG特征向量集合")

    def _ensure_index(self, collection: Collection) -> None:
        # 没有索引时创建 IVF_FLAT 索引，参数使用上方全局配置METRIC/L2、NLIST，无索引向量查询极慢
        if collection.indexes:
            return
        collection.create_index(
            field_name="vector",
            index_params={"metric_type": METRIC_TYPE, "index_type": INDEX_TYPE, "params": {"nlist": NLIST}},
        )

    def _normalize_vector(self, vector: list[float] | np.ndarray) -> list[float]:
        # 强制向量必须是128维float32，维度不符抛异常，统一 Milvus 入库格式
        values = np.asarray(vector, dtype=np.float32)
        if values.ndim != 1 or values.size != VECTOR_DIM:
            raise ValueError(f"PPG特征向量维度必须为{VECTOR_DIM}")
        return values.astype(np.float32).tolist()

    def _parse_search_results(self, results: Any) -> list[dict[str, Any]]:
        # 把 Milvus 原始返回结果整理成普通 dict，后面的代码更好用。
        samples: list[dict[str, Any]] = []
        for hits in results:
            for hit in hits:
                samples.append(
                    {
                        "id": int(hit.id),
                        "distance": float(hit.distance),
                        "sbp": int(hit.entity.get("sbp")),
                        "dbp": int(hit.entity.get("dbp")),
                        "source": str(hit.entity.get("source")),
                        "record_id": int(hit.entity.get("record_id") or 0),
                        "mock_id": str(hit.entity.get("mock_id") or ""),
                        "create_time": int(hit.entity.get("create_time") or 0),
                    }
                )
        return samples


milvus_service = MilvusService()


def init_milvus() -> Collection:
    # 外部初始化 Milvus 时会调用这个。
    return milvus_service.ensure_collection()


def insert_vectors(
    vectors: list[list[float]],
    sbps: list[int],
    dbps: list[int],
    sources: list[str],
    record_ids: list[int] | None = None,
    mock_ids: list[str] | None = None,
) -> list[int]:
    # 给其他模块用的简化入口，内部还是调用 MilvusService。
    return milvus_service.insert_vectors(vectors, sbps, dbps, sources=sources, record_ids=record_ids, mock_ids=mock_ids)


def search_similar(vector: list[float], top_k: int = 5, source: str | None = None, nprobe: int | None = None) -> list[dict]:
    # 给其他模块用的相似检索入口。
    return milvus_service.search_similar(vector, top_k=top_k, source=source, nprobe=nprobe)
