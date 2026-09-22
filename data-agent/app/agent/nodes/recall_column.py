import asyncio

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.prompt.prompt_loader import load_prompt


async def recall_column(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer = runtime.stream_writer
    # 输出内容  stage
    writer({"stage": "召回字段"})

    # 获取向量转化对象
    embedding_client=runtime.context["embedding_client"]

    # 获取向量查询的repository
    column_qdrant_repository=runtime.context["column_qdrant_repository"]
    try:
        # 获取关键字列表
        keywords = state["keywords"]
        # 获取问题
        query = state["query"]

        # 扩展关键字
        # 1.构建提示词
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_column_recall"),input_variables=["query"])
        # 2.构建结构转换器
        output_parser =JsonOutputParser()
        # 3.构建执行链
        chain = prompt | llm | output_parser
        # 4.执行链
        result=await chain.ainvoke({"query":query})
        # 5.合并关键字列表
        keywords = set(keywords+result)
        logger.info(f"扩展后的关键字列表：{keywords}")


        # 去重  {"字段的id":字段对象}
        retrieved_column_map:dict[str,ColumnInfoQdrant]={}
        # 遍历列表召回
        for keyword in keywords:
            # 转换向量
            embedding=await embedding_client.aembed_query(keyword)
            # 查询qdrant
            payloads:list[ColumnInfoQdrant]=await column_qdrant_repository.search(embedding)
            # 遍历查询负载结果
            for payload in payloads:
                # 获取字段id
                column_id = payload["id"]
                # 判断召回map列表中是否存在
                if not  column_id in retrieved_column_map:
                    retrieved_column_map[column_id]=payload


        # 获取召回字段对象列表
        retrieved_columns=list(retrieved_column_map.values())
        logger.info(f"召回字段成功{[retrieved_column_map.keys()]}")
        return {"retrieved_columns":retrieved_columns}
    except Exception as e:
        logger.error(f"召回字段异常：{str(e)}")
        raise