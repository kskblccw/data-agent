import asyncio

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def filter_table(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 休眠1秒
    await asyncio.sleep(1)
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer = runtime.stream_writer
    # 输出内容  stage
    writer({"stage": "过滤表"})

    try:
        # 1.获取状态中需要的信息
        # 获取用户的问题
        query = state["query"]
        # 获取合并表数据信息
        table_infos=state["table_infos"]

        # 2.对接llm过滤无关信息

        # 构建提示词模版对象
        prompt = PromptTemplate(template=load_prompt("filter_table_info"),input_variables=["query","table_infos"])

        # 构建结果转换对象
        output_parser=JsonOutputParser()

        # 构建链
        chain = prompt | llm | output_parser

        # 执行链
        result=await chain.ainvoke({"query":query,"table_infos":table_infos})
        """
        {
        "表名1":["字段1", "字段2", "..."],
        "表名2":["字段1", "字段2", "..."]
        }
        
        """

        # 3.根据返回的结果，剔除无关信息
        for table_info in table_infos[:]:
            # 获取表名
            table_name = table_info["name"]
            # 判断是否存在结果中
            if table_name not in result:
                table_infos.remove(table_info)

            else:
                for column in table_info["columns"][:]:
                    if column["name"] not in result[table_name]:
                        table_info["columns"].remove(column)


        logger.info(f"过滤表信息：{[table_info['name'] for table_info in table_infos]}")

        return {"table_infos":table_infos}
    except Exception as e:
        logger.error(f"过滤表信息异常：{str(e)}")
        raise

