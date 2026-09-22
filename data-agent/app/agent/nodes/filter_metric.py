import asyncio

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def filter_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 休眠1秒
    await asyncio.sleep(1)
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer = runtime.stream_writer
    # 输出内容  stage
    writer({"stage": "过滤指标"})
    try:
        # 1.获取需要的信息
        # 获取用户问题
        query = state["query"]
        # 获取召回的指标
        metric_infos = state["metric_infos"]

        # 2.对接llm
        # 构建提示词对象
        prompt = PromptTemplate(template=load_prompt("filter_metric_info"),input_variables=["query","metric_infos"])

        # 构建输出转换器
        output_parser= JsonOutputParser()

        # 构建链
        chain = prompt | llm | output_parser

        # 执行链
        result = await chain.ainvoke({"query":query,"metric_infos":metric_infos})

        """
        格式：
        [
          "指标名称1",
          "指标名称2",
          "指标名称3"
        ]
            
        
        """
        for metric_info in metric_infos[:]:
            # 判断是否更业务相关
            if metric_info["name"] not in result:
                metric_infos.remove(metric_info)


        logger.info(f"过滤指标成功{ [metric_info['name'] for metric_info in metric_infos]  }")

        return {"metric_infos":metric_infos}
    except Exception as e:
        logger.error(f"过滤指标异常{str(e)}")
        raise