from dataclasses import dataclass
from pathlib import Path

from omegaconf import OmegaConf

@dataclass
class Console:
    enable: str
    level: str

@dataclass
class TextConfig:
    name: str
    age: int
    height: float
    console: Console


# 指定配置文件路径
file_path = Path(__file__).parents[2]/'conf'/'text_conf.yaml'
# 加载配置文件
content = OmegaConf.load(file_path)
# 声明封装结构类型
schema = OmegaConf.structured(TextConfig)
# 合并数据到结构中
text_config:TextConfig=OmegaConf.to_object(OmegaConf.merge(schema,content))

print(text_config)

