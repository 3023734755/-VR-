"""
语义认证图片生成模块

包含在线和本地两种图片生成方式，用于生成语义认证所需的图片。
"""

# 空的__init__.py文件，使该目录成为一个Python包

# 导入主要的生成器类，方便直接从包中导入
from app.utils.image_generation.semantic_auth_generator import SemanticAuthImageGenerator
from app.utils.image_generation.online_generator import OnlineImageGenerator
from app.utils.image_generation.local_generator import TextToImageGenerator

__all__ = [
    'SemanticAuthImageGenerator',
    'OnlineImageGenerator',
    'TextToImageGenerator'
] 