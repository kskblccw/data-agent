import uuid

from fastapi import FastAPI,Request

from app.api.routers.query_router import query_router
from app.core.context import request_id_ctx_var
from app.core.lifespan import lifespan

app = FastAPI(lifespan=lifespan)

# 注册路由
app.include_router(query_router)



@app.middleware("http")
async def set_request_id_middleware(request: Request, call_next):
    # 设置请求的唯一id，用于日志信息的识别
    request_id_ctx_var.set(uuid.uuid4())
    # 执行目标函数
    response = await call_next(request)
    return response