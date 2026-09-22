import asyncio
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def execute_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 休眠1秒
    await asyncio.sleep(1)
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer=runtime.stream_writer
    # 输出内容  stage
    writer({"stage":"执行sql"})
    try:

    # 获取dw
        dw_mysql_repository= runtime.context["dw_mysql_repository"]

        # 1.获取sql
        sql = state["sql"]
        # 2.执行sql
        result =await dw_mysql_repository.execute_sql(sql)

        logger.info(f"执行sql成功：{result}")

        # 3.响应结果
        writer({"result":result})
    except Exception as e:
        logger.error(f"执行sql异常{str(e)}")
        raise
