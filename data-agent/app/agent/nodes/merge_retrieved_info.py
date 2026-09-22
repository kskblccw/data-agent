import asyncio
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState, ColumnInfoState, MetricInfoState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


def convert_column_info_from_mysql_to_qdrant(column_info_mysql:ColumnInfoMySQL):
    return ColumnInfoQdrant(
        id=column_info_mysql.id,
        name=column_info_mysql.name,
        type=column_info_mysql.type,
        role=column_info_mysql.role,
        examples=column_info_mysql.examples,
        description=column_info_mysql.description,
        alias=column_info_mysql.alias,
        table_id=column_info_mysql.table_id,
    )


def convert_column_info_from_qdrant_to_state(column:ColumnInfoQdrant)->ColumnInfoState:
    return ColumnInfoState(
        name=column["name"],
        type=column["type"],
        role=column["role"],
        examples=column["examples"],
        description=column["description"],
        alias=column["alias"]
    )


def convert_metric_info_from_qdrant_to_state(retrieved_metric:MetricInfoQdrant)->MetricInfoState:
    return MetricInfoState(
        name=retrieved_metric["name"],
        description=retrieved_metric["description"],
        relevant_columns=retrieved_metric["relevant_columns"],
        alias=retrieved_metric["alias"]
    )


async def merge_retrieved_info(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 休眠1秒
    await asyncio.sleep(1)
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer = runtime.stream_writer
    # 输出内容  stage
    writer({"stage": "合并召回信息"})
    try:
        # 获取原数据库查询对象
        meta_mysql_repository =runtime.context["meta_mysql_repository"]
        # 合并表信息结果封装
        table_infos: list[TableInfoState] = []
        # 获取召回字段列表
        retrieved_columns: list[ColumnInfoQdrant]=state["retrieved_columns"]
        # 获取召回的取值列表
        retrieved_values: list[ValueInfoEs]=state["retrieved_values"]
        # 获取召回的指标列表
        retrieved_metrics: list[MetricInfoQdrant]=state["retrieved_metrics"]


        # 转化类型dict，避免字段重复 {key:column_id:ColumnInfoQdrant}
        retrieved_columns_map:dict[str,ColumnInfoQdrant]={retrieved_column["id"]: retrieved_column for retrieved_column in retrieved_columns}

        # 补充指标中关联的字段信息
        for metric in retrieved_metrics:
            # 获取指标关联的列的结果
            relevant_columns:list[str]=metric["relevant_columns"]
            # 遍历处理关联列信息
            for relevant_column in relevant_columns:
                # 判断是否已经被召回
                if relevant_column not in retrieved_columns_map:
                    # 根据字段id查询字段信息
                    column_info_mysql:ColumnInfoMySQL=await  meta_mysql_repository.get_column_info_by_id(relevant_column)
                    # 转换类型
                    column_info_qdrant:ColumnInfoQdrant =convert_column_info_from_mysql_to_qdrant(column_info_mysql)
                    # 存储
                    retrieved_columns_map[relevant_column]=column_info_qdrant

        # 字段取值处理
        for retrieved_value in retrieved_values:
            # 获取对应的字段id
            column_id =retrieved_value["column_id"]

            # 获取召回的字段值value
            column_value =retrieved_value["value"]
            # 判断是已经被召回
            if column_id not in retrieved_columns_map:
                # 根据id查询字段数据
                # 根据字段id查询字段信息
                column_info_mysql: ColumnInfoMySQL = await  meta_mysql_repository.get_column_info_by_id(column_id)
                # 转换类型
                column_info_qdrant: ColumnInfoQdrant = convert_column_info_from_mysql_to_qdrant(column_info_mysql)
                # 存储
                retrieved_columns_map[column_id] = column_info_qdrant

            # 处理值信息
            if column_value not in retrieved_columns_map[column_id]['examples']:
                # 存储值到关联列表中
                retrieved_columns_map[column_id]["examples"].append(column_value)


        # 定义表封装结构 {表id:List{ColumnInfoQdrant}}
        table_to_column_map:dict[str,list[ColumnInfoQdrant]]={}
        # 遍历封装
        for column in retrieved_columns_map.values():
            # 获取表id
            table_id =column["table_id"]
            # 判断
            if table_id not in  table_to_column_map:
                table_to_column_map[table_id]=[]
            # 添加字段到表中
            table_to_column_map[table_id].append(column)


        # 关键当前相关表的主外键字段信息
        for table_id in table_to_column_map.keys():
            # 根据表id查询表的主外键
            key_columns:list[ColumnInfoMySQL]=await meta_mysql_repository.get_key_columns_by_table_id(table_id)
            # 获取已有的所有字段的id
            ids=[column['id'] for column in table_to_column_map[table_id]]
            # 遍历存储主外键
            for key_column in key_columns:
                # 获取id
                column_id = key_column.id
                # 判断是否已经存在
                if column_id not in ids:
                    table_to_column_map[table_id].append(convert_column_info_from_mysql_to_qdrant(key_column))



        # 转换表结构封装
        for table_id,column_list in table_to_column_map.items():

            # 根据表id查询表信息
            table_info_mysql: TableInfoMySQL =await meta_mysql_repository.get_table_info_by_id(table_id)

            # 获取当前表的所有字段信息
            columns=[convert_column_info_from_qdrant_to_state(column) for column in column_list]

            #  转换类型
            table_info=TableInfoState(
                name=table_info_mysql.name,
                role=table_info_mysql.role,
                description=table_info_mysql.description,
                columns=columns
            )
            table_infos.append(table_info)


        logger.info(f'合并后的表信息数据{[table_info["name"] for table_info in table_infos]}')
        # 指标转换结构
        metric_infos:list[MetricInfoState]=[convert_metric_info_from_qdrant_to_state(retrieved_metric) for retrieved_metric in retrieved_metrics]

        logger.info(f'合并后的指标信息{[metric_info["name"] for metric_info in metric_infos]}')
        return {"table_infos":table_infos,"metric_infos":metric_infos}
    except Exception as e:
        logger.error(f"合并召回信息异常{str(e)}")
        raise




