from elasticsearch import AsyncElasticsearch

from app.models.es.value_info_es import ValueInfoEs


class ValueEsRepository:
    es_index_name="data-agent-values"
    es_index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_max_word"},
            "type": {"type": "keyword"},
            "column_id": {"type": "keyword"},
            "column_name": {"type": "keyword"},
            "table_id": {"type": "keyword"},
            "table_name": {"type": "keyword"},
        }
    }

    def __init__(self,client:AsyncElasticsearch):
        self.client=client

    async def ensure_index(self):
        """
        确保存储字段值的索引存在
        :return:
        """
        # 判断是否已经存在
        if not await self.client.indices.exists(index=self.es_index_name):
             await self.client.indices.create(
                index=self.es_index_name,
                mappings=self.es_index_mappings,
            )



    async def save_column_values(self, value_infos:list[ValueInfoEs],batch_size=10):
        """
        保存字段值到es

        :param value_infos:
        :return:
        """
        # 批次保存数据
        for i in range(0,len(value_infos),batch_size):
            # 获取批次数据
            batch_value_infos= value_infos[i:i+batch_size]
            # 定义列表接收es结构保存数据
            operations:list=[]
            # 遍历转换结构
            for batch_value_info in batch_value_infos:
                # 添加索引声明
                operations.append(
                    {
                        "index": {
                            "_index": self.es_index_name
                        }
                    }
                )
                # 添加value数据
                operations.append(batch_value_info)
            # 保存批次数据
            await self.client.bulk(
                operations=operations,
            )

    async def search(self, keyword:str)->list[ValueInfoEs]:


        resp = await  self.client.search(
            index=self.es_index_name,
            query={
                "match": {
                    "value": keyword
                }
            },
        )
        # 返回结果
        return [result['_source'] for result in resp['hits']['hits']]

