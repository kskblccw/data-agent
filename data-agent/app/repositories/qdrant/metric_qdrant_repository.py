from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

from app.conf.app_config import app_config
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


class MetricQdrantRepository:
    # 集合存储名称
    collection_name="data-agent-metrics"
    def __init__(self,client:AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        """
        确保存储指标的集合存在
        :return:
        """
        # 判断集合是否存在
        if not await self.client.collection_exists(collection_name=self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=app_config.qdrant.embedding_size, distance=Distance.COSINE),
            )


    async def upsert_metrics(self, ids:list[str], embeddings:list[list[float]], payloads:list[MetricInfoQdrant],batch_size=10):
        """
        保存指标信息到qdrant中
        :param ids:
        :param embeddings:
        :param payloads:
        :return:
        """
        # 整合指标列表
        zipped = list(zip(ids,embeddings,payloads))
        # 遍历批次处理
        for i in range(0,len(zipped),batch_size):
            # 获取批次数据
            batch_zipped = zipped[i:i+batch_size]
            # 转化类型
            points = [
                PointStruct(
                    id=id,
                    vector=embeddings,
                    payload=payload
                )
                for id,embeddings,payload in batch_zipped]

            # 保存
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

    async def search(self, embedding: list[float]):

        search_result = await self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            score_threshold=0.6
        )

        return [point.payload for point in search_result.points]
