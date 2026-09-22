import asyncio

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompt.prompt_loader import load_prompt


async def recall_value(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer = runtime.stream_writer
    # 输出内容  stage
    writer({"stage": "召回字段值"})

    try:
        # 获取es查询对象
        value_es_repository=runtime.context["value_es_repository"]

        # 获取关键字列表
        keywords = state["keywords"]
        # 获取问题
        query = state["query"]

        # 扩展关键字
        # 1.构建提示词
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_value_recall"), input_variables=["query"])
        # 2.构建结构转换器
        output_parser = JsonOutputParser()
        # 3.构建执行链
        chain = prompt | llm | output_parser
        # 4.执行链
        result = await chain.ainvoke({"query": query})
        # 5.合并关键字列表
        keywords = set(keywords + result)
        logger.info(f"扩展后的关键字列表：{keywords}")

        # 去重  {"字段值的id":字段值}
        retrieved_value_map: dict[str, ValueInfoEs] = {}
        # 遍历列表召回
        for keyword in keywords:
            # 查询es
            es_values: list[ValueInfoEs] = await value_es_repository.search(keyword)
            # 遍历查询负载结果
            for value in es_values:
                # 获取指标id
                value_id = value["id"]
                # 判断召回map列表中是否存在
                if not value_id in retrieved_value_map:
                    retrieved_value_map[value_id] = value

        # 获取召回字段对象列表
        retrieved_values = list(retrieved_value_map.values())
        logger.info(f"召回字段取值成功{[retrieved_value_map.keys()]}")
        return {"retrieved_values": retrieved_values}
    except Exception as e:
        logger.error(f"召回字段取值失败：{str(e)}")
        raise


