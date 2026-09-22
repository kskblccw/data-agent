from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

from app.conf.app_config import app_config
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant


class ColumnQdrantRepository:

     # 定义字段存储向量集合名称
     collection_name ="data-agent-column"

     def __init__(self,client:AsyncQdrantClient):
         self.client = client

     async def ensure_collection(self):
         """
         确保存储字段向量的集合存在
         :return:
         """
         if not await self.client.collection_exists(collection_name=self.collection_name):
             await self.client.create_collection(
                 collection_name=self.collection_name,
                 vectors_config=VectorParams(size=app_config.qdrant.embedding_size, distance=Distance.COSINE),
             )

     async def upsert_embedding(self, ids:list[str], embeddings:list[list[float]], payloads:list[ColumnInfoQdrant],batch_size:int=10):
         """
         存储字段向量到qdrant
         :param ids:
         :param embeddings:
         :param payloads:
         :return:
         """
         # 按照顺序组合多个列表数据 [(id,embedding,payload),(id,embedding,payload)]
         zipped = list(zip(ids,embeddings,payloads))
         # 批量存储
         for i in range(0,len(zipped),batch_size):
             # 获取批次数据
             batch_zipped= zipped[i:i+batch_size]
             # 批次数据[(id,embedding,payload)]转换成 [PointStruct]

             points = [ PointStruct(
                         id=id,
                         vector=embedding,
                         payload=payload
                     ) for id,embedding,payload  in batch_zipped]
             # 保存批次数据
             await self.client.upsert(
                 collection_name=self.collection_name,
                 points=points,
             )

     async def search(self, embedding:list[float]):

         search_result = await self.client.query_points(
             collection_name=self.collection_name,
             query=embedding,
             score_threshold=0.6
         )

         return [ point.payload for point in search_result.points]


