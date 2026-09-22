import asyncio
from pathlib import Path

from Lib import argparse

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.msyql.dw_mysql_repository import DwMysqlRepository
from app.repositories.msyql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.meta_knowledge_service import MetaKnowledgeService


async def build(file_path:Path):
    # 初始化客户端对象
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()

    # 获取session
    async with meta_mysql_client_manager.session_factory() as meta_session ,dw_mysql_client_manager.session_factory() as dw_session:


        # 创建repository对象
        meta_mysql_repository = MetaMysqlRepository(meta_session)
        dw_mysql_repository = DwMysqlRepository(dw_session)
        column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
        value_es_repository = ValueEsRepository(es_client_manager.client)
        metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)
        # 创建service对象
        meta_knowledge_service= MetaKnowledgeService(
            meta_mysql_repository=meta_mysql_repository,
            dw_mysql_repository=dw_mysql_repository,
            column_qdrant_repository=column_qdrant_repository,
            embedding_client=embedding_client_manager.client,
            value_es_repository=value_es_repository,
            metric_qdrant_repository=metric_qdrant_repository
        )
        # 调用业务函数
        await meta_knowledge_service.build(file_path)
    # 释放资源
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await es_client_manager.close()


if __name__ == '__main__':


    # 构建解析对象
    parser = argparse.ArgumentParser()
    # 设置解析配置
    parser.add_argument('-c', '--conf')  # 接受一个值的选项
    # 解析终端指令
    args = parser.parse_args()
    file_path=Path(args.conf)

    asyncio.run(build(file_path))
