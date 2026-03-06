import logging
from sqlalchemy import text
from sqlalchemy.sql.expression import func
from app import db
from app.models.models import SemanticLibrary

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def execute_query(query, params=None, fetch_all=True):
    """
    使用 SQLAlchemy 执行原生 SQL 查询，保持与旧接口兼容
    """
    try:
        # 将 SQL 语句转换为 SQLAlchemy 的 text 对象
        sql = text(query)
        
        # 执行查询
        result = db.session.execute(sql, params)
        
        # 将结果转换为字典列表，模拟 pymysql 的 DictCursor
        if fetch_all:
            return [dict(row) for row in result.mappings().all()]
        else:
            row = result.mappings().first()
            return dict(row) if row else None
            
    except Exception as e:
        logger.error(f"执行查询失败: {e}")
        logger.error(f"查询: {query}")
        return []

def execute_update(query, params=None):
    """
    使用 SQLAlchemy 执行更新操作
    """
    try:
        sql = text(query)
        result = db.session.execute(sql, params)
        db.session.commit()
        return result.rowcount
    except Exception as e:
        db.session.rollback()
        logger.error(f"执行更新失败: {e}")
        return 0

def get_semantic_labels(category=None):
    """
    获取语义标签
    """
    try:
        if category:
            labels = SemanticLibrary.query.filter_by(category=category).all()
        else:
            labels = SemanticLibrary.query.all()
        
        # 保持返回格式一致（字典列表）
        return [{'id': l.id, 'semantic_text': l.semantic_text, 'category': l.category} for l in labels]
    except Exception as e:
        logger.error(f"获取语义标签失败: {e}")
        return []

def get_random_semantic_labels(category, count=3):
    """
    随机获取指定数量的语义标签
    """
    try:
        # 使用 SQLAlchemy 的随机排序
        labels = SemanticLibrary.query.filter_by(category=category).order_by(func.random()).limit(count).all()
        return [{'id': l.id, 'semantic_text': l.semantic_text, 'category': l.category} for l in labels]
    except Exception as e:
        logger.error(f"获取随机语义标签失败: {e}")
        return []

def test_connection():
    """测试数据库连接"""
    try:
        # 简单执行一个查询来测试连接
        db.session.execute(text("SELECT 1"))
        logger.info(f"数据库连接成功 (通过 SQLAlchemy)")
        return True
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False

if __name__ == "__main__":
    # 测试数据库连接
    # 注意：直接运行此脚本可能会失败，因为它需要 Flask 应用上下文
    # 应该在 Flask 应用上下文中调用这些函数
    logger.warning("请在 Flask 应用上下文中调用此模块的函数")
