import asyncio

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.prompt.prompt_loader import load_prompt


async def recall_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 休眠1秒
    await asyncio.sleep(1)
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer = runtime.stream_writer
    # 输出内容  stage
    writer({"stage": "召回指标"})
    try:
        # 获取向量转换对象
        embedding_client= runtime.context["embedding_client"]

        # 获取指标查询对象
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]

        # 获取关键字列表
        keywords = state["keywords"]
        # 获取问题
        query = state["query"]

        # 扩展关键字
        # 1.构建提示词
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_metric_recall"), input_variables=["query"])
        # 2.构建结构转换器
        output_parser = JsonOutputParser()
        # 3.构建执行链
        chain = prompt | llm | output_parser
        # 4.执行链
        result = await chain.ainvoke({"query": query})
        # 5.合并关键字列表
        keywords = set(keywords + result)
        logger.info(f"扩展后的关键字列表：{keywords}")


        # 召回指标信息
        # 去重  {"指标的id":指标对象}
        retrieved_metric_map: dict[str, MetricInfoQdrant] = {}
        # 遍历列表召回
        for keyword in keywords:
            # 转换向量
            embedding = await embedding_client.aembed_query(keyword)
            # 查询qdrant
            payloads: list[MetricInfoQdrant] = await metric_qdrant_repository.search(embedding)
            # 遍历查询负载结果
            for payload in payloads:
                # 获取指标id
                metric_id = payload["id"]
                # 判断召回map列表中是否存在
                if not metric_id in retrieved_metric_map:
                    retrieved_metric_map[metric_id] = payload

        # 获取召回字段对象列表
        retrieved_metrics = list(retrieved_metric_map.values())
        logger.info(f"召回指标成功{[retrieved_metric_map.keys()]}")
        return {"retrieved_metrics": retrieved_metrics}
    except Exception as e:
        logger.error(f"召回指标异常，{str(e)}")
        raise



