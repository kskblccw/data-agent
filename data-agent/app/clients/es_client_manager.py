import asyncio
from typing import Optional

from elasticsearch import AsyncElasticsearch

from app.conf.app_config import app_config, ESConfig


class EsClientManager:
    def __init__(self,config:ESConfig):
        self.client:Optional[AsyncElasticsearch] = None
        self.config=config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"
    def init(self):
        self.client = AsyncElasticsearch(
            hosts=[self._get_url()],
        )

    async def close(self):
        await self.client.close()


es_client_manager = EsClientManager(app_config.es)


if __name__ == '__main__':

    # 初始化es客户端
    es_client_manager.init()
    # 获取client
    client = es_client_manager.client

    async def test():
        """
        1.判断是否存在索引
        2.不存在创建索引
        3.添加文档
        4.检索文档

        :return:
        """
        # 判断是否存在
        if not await client.indices.exists(index="my_books"):
            # 创建
            resp = await client.indices.create(
                index="my_books",
                mappings={
                    "dynamic": False,
                    "properties": {
                        "name": {
                            "type": "text"
                        },
                        "author": {
                            "type": "text"
                        },
                        "release_date": {
                            "type": "date",
                            "format": "yyyy-MM-dd"
                        },
                        "page_count": {
                            "type": "integer"
                        }
                    }
                },
            )

        # 添加文档
        # resp =await  client.bulk(
        #     operations=[
        #         {
        #             "index": {
        #                 "_index": "my_books"
        #             }
        #         },
        #         {
        #             "name": "Revelation Space",
        #             "author": "Alastair Reynolds",
        #             "release_date": "2000-03-15",
        #             "page_count": 585
        #         },
        #         {
        #             "index": {
        #                 "_index": "my_books"
        #             }
        #         },
        #         {
        #             "name": "1984",
        #             "author": "George Orwell",
        #             "release_date": "1985-06-01",
        #             "page_count": 328
        #         }
        #     ],
        # )
        # print(resp)

        # 检索
        resp =await  client.search(
            index="my_books",
            query={
                "match": {
                    "author": "Orwell"
                }
            },
        )

        for hit in  resp['hits']['hits']:

            print(hit['_source'])

        await client.close()



    asyncio.run(test())









