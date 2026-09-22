import asyncio
from typing import Optional

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.conf.app_config import app_config, EmbeddingConfig


class EmbeddingClientManager:

    def __init__(self,config:EmbeddingConfig):
        self.client: Optional[HuggingFaceEndpointEmbeddings] = None
        self.config = config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = HuggingFaceEndpointEmbeddings(
            model=self._get_url()
        )
embedding_client_manager =EmbeddingClientManager(app_config.embedding)


if __name__ == '__main__':
    # 初始化对象
    embedding_client_manager.init()

    async def test():
        # 获取对象
        client = embedding_client_manager.client

        # 定义文本
        text = "你好，我爱中国"
        # 转化向量
        # result=await client.aembed_query(text)
        result=await client.aembed_documents([text])

        print(type(result))
        print(len(result))
        print(result)

    asyncio.run(test())











