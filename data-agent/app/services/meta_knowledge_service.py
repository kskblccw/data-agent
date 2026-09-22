import uuid
from pathlib import Path

from Lib.dataclasses import asdict
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf

from app.conf.meta_config import MetaConfig
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.msyql.dw_mysql_repository import DwMysqlRepository
from app.repositories.msyql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class MetaKnowledgeService:
    def __init__(self,
                 meta_mysql_repository:MetaMysqlRepository,
                 dw_mysql_repository:DwMysqlRepository,
                 column_qdrant_repository:ColumnQdrantRepository,
                 embedding_client:HuggingFaceEndpointEmbeddings,
                 value_es_repository:ValueEsRepository,
                 metric_qdrant_repository:MetricQdrantRepository,
                 ):
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.embedding_client = embedding_client
        self.value_es_repository=value_es_repository
        self.metric_qdrant_repository=metric_qdrant_repository

    async def build(self,file_path:Path):

        # 加载配置文件读取数据
        # 加载配置配置内容
        context = OmegaConf.load(file_path)
        # 创建数据封装结构
        schema = OmegaConf.structured(MetaConfig)
        # 合并并封装对象
        meta_config:MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema,context))
        logger.info("加载配置文件完成")


        # 判断是否存在表信息的构建
        if meta_config.tables:
            # 保存表信息到meta数据库
            column_infos:list[ColumnInfoMySQL]=await self._save_talbe_info_to_meta_db(meta_config)
            logger.info("保存表信息到meta数据库")
            # 为字段信息构建向量索引
            await self._save_column_info_to_qdrant(column_infos)
            logger.info("为字段构建向量索引")
            await self._save_value_info_to_es(column_infos,meta_config)
            logger.info("为字段值构建全文索引")


        if meta_config.metrics:
            # 保存指标信息到meta数据库
            metric_infos:list[MetricInfoMySQL]=await self._save_metric_info_to_meta_db(meta_config)
            logger.info("保存指标信息到meta数据库")
            # 为指标信息构建向量索引
            await self._save_metric_info_to_qdrant(metric_infos)
            logger.info("为指标构建向量索引")


    async def _save_talbe_info_to_meta_db(self, meta_config:MetaConfig):
        # 定义表信息封装列表
        table_infos: list[TableInfoMySQL] = []
        # 定义字段信息封装列表
        column_infos: list[ColumnInfoMySQL] = []

        for table in meta_config.tables:
            # table--TableInfoMysql
            table_info_mysql = TableInfoMySQL(
                id=table.name,
                name=table.name,
                role=table.role,
                description=table.description,

            )
            table_infos.append(table_info_mysql)
            # 查询表字段的类型数据
            column_types: dict[str, str] = await self.dw_mysql_repository.get_column_types(table.name)

            # 获取字段列表，封装字段数据
            for column in table.columns:
                # 查询字段值
                column_values: list[str] = await self.dw_mysql_repository.get_column_values(table.name, column.name)

                column_info = ColumnInfoMySQL(
                    id=f"{table.name}.{column.name}",
                    name=column.name,
                    type=column_types[column.name],
                    role=column.role,
                    examples=column_values,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name,
                )
                column_infos.append(column_info)
        # 保存到meta数据库
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_table_infos(table_infos)
            await self.meta_mysql_repository.save_column_infos(column_infos)

        return column_infos

    def _convert_column_info_from_mysql_to_qdrant(self, column_info:ColumnInfoMySQL):
        # return ColumnInfoQdrant(
        #     **asdict(column_info)
        # )
        return ColumnInfoQdrant(
            id=column_info.id,
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            description=column_info.description,
            alias=column_info.alias,
            table_id=column_info.table_id
        )

    async def _save_column_info_to_qdrant(self, column_infos:list[ColumnInfoMySQL]):
        # 确保存储字段数据的向量集合存在
        await self.column_qdrant_repository.ensure_collection()

        # 构建向量存储集合
        points: list[dict] = []
        # 遍历字段列表封装向量存储结构
        for column_info in column_infos:
            # name
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": column_info.name,
                "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
            })

            # description
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": column_info.description,
                "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
            })

            # alias
            for alia in column_info.alias:
                points.append({
                    "id": uuid.uuid4(),
                    "embedding_text": alia,
                    "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
                })

        # 获取所有向量文本
        embeddings_texts = [point["embedding_text"] for point in points]
        # 定义批次数量
        batch_size = 10
        # 定义向量列表
        embeddings: list[list[float]] = []
        # 遍历向量文本列表
        for i in range(0, len(embeddings_texts), batch_size):
            # 获取批次数据
            batch_embedding_texts = embeddings_texts[i:i + batch_size]
            # 转换向量 list[list[float]]
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
            # 收集批次数据
            embeddings.extend(batch_embeddings)

        # 获取所有的id
        ids = [point['id'] for point in points]
        # 获取所有负载
        payloads = [point['payload'] for point in points]

        # 存储字段向量数据到qdrant
        await self.column_qdrant_repository.upsert_embedding(ids, embeddings, payloads)

    async def _save_value_info_to_es(self, column_infos:list[ColumnInfoMySQL],meta_config:MetaConfig):
        # 确保存储字段值的索引存在
        await self.value_es_repository.ensure_index()

        # 获取所有字段的值是否进行全文索引的标识
        column2sync: dict[str, bool] = {}
        for table in meta_config.tables:
            for column in table.columns:
                column2sync[column.name] = column.sync

        # 收集所有字段值数据
        value_infos: list[ValueInfoEs] = []
        # 为字段值信息构建全文索引
        for column_info in column_infos:
            # 获取当前字段的索引标识
            sync = column2sync[column_info.name]
            if sync:
                # 根据列名查询这一列的所有值
                column_values: list[str] = await self.dw_mysql_repository.get_column_values(column_info.table_id,
                                                                                            column_info.name,
                                                                                            limit=10000)

                # 遍历字段值列表
                for column_value in column_values:
                    # 创建对象
                    value_info_es = ValueInfoEs(
                        id=f"{column_info.id}.{column_value}",
                        value=column_value,
                        type=column_info.type,
                        column_id=column_info.id,
                        column_name=column_info.name,
                        table_id=column_info.table_id,
                        table_name=column_info.table_id
                    )
                    value_infos.append(value_info_es)
        # 保存到es
        await self.value_es_repository.save_column_values(value_infos)

    async def _save_metric_info_to_meta_db(self, meta_config:MetaConfig):
        # 定义列表收集指标
        metric_infos: list[MetricInfoMySQL] = []
        # 定义列表收集字段指标数据
        column_metrics: list[ColumnMetricMySQL] = []

        for metric in meta_config.metrics:
            # 构建指标对象
            metric_info_mysql = MetricInfoMySQL(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            metric_infos.append(metric_info_mysql)

            # 构建指标字段关联对象
            for relevant_column in metric.relevant_columns:
                column_metric_mysql = ColumnMetricMySQL(
                    column_id=relevant_column,
                    metric_id=metric.name
                )
                column_metrics.append(column_metric_mysql)
        # 保存指标信息
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_metric_infos(metric_infos)
            await self.meta_mysql_repository.save_column_metrics(column_metrics)
        return metric_infos

    def _convert_metric_from_mysql_to_qdrant(self, metric_info:MetricInfoMySQL):
        return MetricInfoQdrant(
            id=metric_info.id,
            name=metric_info.name,
            description=metric_info.description,
            relevant_columns=metric_info.relevant_columns,
            alias=metric_info.alias


        )

    async def _save_metric_info_to_qdrant(self, metric_infos:list[MetricInfoMySQL]):
        # 确保指标存储的集合存在
        await self.metric_qdrant_repository.ensure_collection()
        # 定义列表收集向量保存对象
        points: list[dict] = []

        for metric_info in metric_infos:
            # name
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": metric_info.name,
                "payload": self._convert_metric_from_mysql_to_qdrant(metric_info)
            })
            # description
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": metric_info.description,
                "payload": self._convert_metric_from_mysql_to_qdrant(metric_info)
            })
            # alias
            for alia in metric_info.alias:
                points.append({
                    "id": uuid.uuid4(),
                    "embedding_text": alia,
                    "payload": self._convert_metric_from_mysql_to_qdrant(metric_info)
                })
        # 获取所有的向量文本
        embedding_texts = [point['embedding_text'] for point in points]
        # 转换数据
        batch_size = 20
        # 收集向量
        embeddings: list[list[float]] = []
        # 遍历转换向量
        for i in range(0, len(embedding_texts), batch_size):
            # 获取批量文本
            batch_embedding_texts = embedding_texts[i:i + batch_size]
            # 转换向量
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
            embeddings.extend(batch_embeddings)

        # 获取id
        ids = [point['id'] for point in points]
        # 获取负载
        payloads = [point['payload'] for point in points]
        # 保存数据到qdrant
        await self.metric_qdrant_repository.upsert_metrics(ids, embeddings, payloads)