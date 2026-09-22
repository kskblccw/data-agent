import asyncio
from datetime import datetime

from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoState
from app.core.log import logger


async def add_extra_context(state:DataAgentState,runtime:Runtime[DataAgentContext]):

    # 休眠1秒
    await asyncio.sleep(1)
    # 获取流输出器
    # writer = get_stream_writer()
    # runtime中获取
    writer=runtime.stream_writer
    # 输出内容  stage
    writer({"stage":"添加额外上下文信息"})

    try:
        # 获取dw的repository
        dw_mysql_repository= runtime.context["dw_mysql_repository"]

        # 1. 时间信息
        # 获取时间 --年月日时分秒
        today=datetime.today()
        # 年月日
        date =today.strftime("%Y-%m-%d")
        # 星期
        weekday=today.strftime("%A")
        # 季度
        quarter = f"Q{(today.month-1)//3+1}"

        # 封装时间信息
        date_info_state= DateInfoState(
            date=date,
            weekday=weekday,
            quarter=quarter
        )

        # 2.数据库信息

        db_info =await dw_mysql_repository.get_db_info()
        logger.info(f"额外上下文信息添加，日期信息{date_info_state},数据库信息{db_info}")
        return {"date_info":date_info_state,"db_info":db_info}
    except Exception as e:
        logger.error(f"添加额外上下文信息异常{str(e)}")
        raise
