import asyncio
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def validate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 休眠1秒
    await asyncio.sleep(1)
    # 获取流输出器

    # writer = get_stream_writer()
    # runtime中获取
    writer = runtime.stream_writer
    # 输出内容  stage
    writer({"stage": "校验sql"})

    try:
        # 获取sql
        sql =state["sql"]
        # 获取dw的repository
        dw_msql_repository = runtime.context["dw_mysql_repository"]
        # 执行校验
        await dw_msql_repository.validate_sql(sql)
        logger.info(f"校验sql正确：{sql}")
        return {"error":None}
    except Exception as e:
        logger.error(f"校验sql异常：{str(e)}")
        return {"error":str(e)}
