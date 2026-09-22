import asyncio
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker

from app.conf.app_config import app_config, DBConfig


class MysqlClientManager:
    def __init__(self, config: DBConfig):
        self.config = config
        # self.engine:AsyncEngine|None=None
        self.engine: Optional[AsyncEngine] = None
        self.session_factory = None

    def _get_url(self):
        return (f"mysql+asyncmy://{self.config.user}"
                f":{self.config.password}@{self.config.host}"
                f":{self.config.port}/{self.config.database}?charset=utf8mb4")

    def init(self):
        self.engine = create_async_engine(
            url=self._get_url(),
            pool_size=10,
            pool_pre_ping=True
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=True,
            autobegin=True,
            expire_on_commit=False

        )



    async def close(self):
        await self.engine.dispose()


dw_mysql_client_manager = MysqlClientManager(app_config.db_dw)

meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    # 初始化客户端对象
    dw_mysql_client_manager.init()

    # 定义异步函数
    async def test():

        # 获取会话操作数据库
        # async with AsyncSession(bind=dw_mysql_client_manager.engine,autoflush=True,autobegin=True,expire_on_commit=False) as session:
        async with dw_mysql_client_manager.session_factory() as session:

            # 定义sql
            sql ="select * from fact_order limit 10"
            # 执行sql --> result是封装了结果的容器
            result =await session.execute(text(sql))
            # 获取
            # [(),(),()]
            # rows = result.fetchall()
            # rows1 = result.fetchone()
            # rows2 = result.scalars().fetchall()
            # [{},{}]
            rows3 = result.mappings().fetchall()
            print(type(rows3[0]))

        await dw_mysql_client_manager.close()

    asyncio.run(test())
