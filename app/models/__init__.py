"""
数据模型包

包含所有数据库模型定义。
"""

# 确保首先导入所有基础模型
from app.models.models import User, SemanticLibrary, SemanticPassword, CompanionSemantic

# 然后导入依赖于基础模型的专用模型
from app.models.auth_challenge import AuthChallenge
from app.models.auth_images import AuthImage
