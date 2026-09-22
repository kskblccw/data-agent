import asyncio

import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def generate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 休眠1秒
    await asyncio.sleep(1)
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer = runtime.stream_writer
    # 输出内容  stage
    writer({"stage": "生成sql"})

    try:
        # 1.获取所有需要的数据
        # 获取用户的问题
        query = state["query"]
        # 获取表信息
        table_infos = state["table_infos"]
        # 获取指标
        metric_infos = state["metric_infos"]
        # 时间信息
        date_info = state["date_info"]
        # 数据库信息
        db_info = state["db_info"]

        # 2.对接llm生成sql
        # 构建提示词
        prompt= PromptTemplate(template=load_prompt("generate_sql"),input_variables=["query","table_infos","metric_infos","date_info","db_info"])
        # 构建输出转换器
        output_parser= StrOutputParser()
        # 构建链
        chain = prompt | llm | output_parser
        # 执行链
        sql=await chain.ainvoke({
            "query":query,
            "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
            "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
            "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
        })

        logger.info(f"生成sql语句成功，{sql}")
        return {"sql":sql}
    except Exception as e:
        logger.error(f"生成sql语句异常{str(e)}")
        raise



















