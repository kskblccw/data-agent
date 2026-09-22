from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DwMysqlRepository:
    def __init__(self,session:AsyncSession):
        self.session = session

    async def get_column_types(self, table_name:str)->dict[str,str]:
        """
        根据表查询表中所有字段的类型

        :param table_name:
        :return: {'字段名':'字段类型'，'字段名':'字段类型'}
        """
        # 定义sql语句
        sql = f"show columns from  {table_name}"
        # 执行sql
        result=await self.session.execute(text(sql))
        #获取结果 [(row(Field=order_id,Type=varchar)),(),()]
        return {row.Field: row.Type for row in result.fetchall()}

    async def get_column_values(self, table_name:str, column_name:str,limit:int=10):
        """
        查询字段值
        :param table_name:
        :param column_name:
        :return:
        """
        # 定义sql
        sql = f"select distinct {column_name}  from {table_name} limit {limit}"
        # 执行sql
        result = await self.session.execute(text(sql))
        # 解析结果
        return result.scalars().fetchall()

    async def get_db_info(self):

        # 获取版本
        result =await self.session.execute(text("select version()"))
        # 获取版本信息
        version=result.scalar()

        # 获取方言
        dialect = self.session.get_bind().dialect.name


        return {"version":version,"dialect":dialect}

    async def validate_sql(self, sql:str):
        # i = 1/0
        await self.session.execute(text(f"explain {sql}"))

    async def execute_sql(self, sql:str):

        # 执行sql
        result = await self.session.execute(text(sql))
        #结果 [row()，row(),row()]--->[{RowMapping},{RowMapping},{RowMapping}]
        # return result.mappings().fetchall()
        return [dict(row) for row in result.mappings().fetchall()]
