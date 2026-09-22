import asyncio
import random
import uuid
from typing import Optional


from qdrant_client import AsyncQdrantClient, models

from app.conf.app_config import app_config, QdrantConfig
from app.core.log import logger


class QdrantClientManager:
    def __init__(self,config:QdrantConfig):
        self.client: Optional[AsyncQdrantClient] = None
        self.config = config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = AsyncQdrantClient(url=self._get_url())

    async def close(self):
        await self.client.close()


qdrant_client_manager = QdrantClientManager(app_config.qdrant)


if __name__ == '__main__':
    qdrant_client_manager.init()
    """
    测试：
    1.测试判断指定集合是否存在
    2.不存在创建集合
    3.存储向量到集合中
    4.查询向量
    
    
    """
    # 获取客户端对象
    client = qdrant_client_manager.client

    async def test():
        # 判读指定的my_collection是否存在
        # if not await client.collection_exists("my_collection"):
        #     # 创建集合
        #     await client.create_collection(
        #         collection_name="my_collection",
        #         vectors_config=models.VectorParams(size=app_config.qdrant.embedding_size, distance=models.Distance.COSINE),
        #     )

        # 存储向量
        await client.upsert(
            collection_name="my_collection",
            points=[
                models.PointStruct(
                    id=uuid.uuid4(),
                    vector=[ random.random() for _ in range(1024)],
                    payload={"color": "red", "rand_number": uuid.uuid4()}
                )
                for _ in range(10)
            ],
        )

        # 查询
        res = await client.query_points(
            collection_name="my_collection",
            query=[ random.random() for _ in range(1024)],  # type: ignore
            limit=10,
            score_threshold=0.75
        )

        for point in res.points:
            logger.info(point)
        await client.close()

    asyncio.run(test())












