from openai import BaseModel


class QuerySchema(BaseModel):
    query: str
