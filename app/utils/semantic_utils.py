"""
语义工具模块 - 提供语义相关的工具函数
"""
import random
from app.models.models import SemanticLibrary
from app import db
from flask import current_app

def get_semantic_by_category(category, limit=None, random_select=False):
    """
    按类别获取语义标签
    
    Args:
        category (str): 语义类别 ('subject', 'environment', 'behavior')
        limit (int, optional): 返回的最大数量，None表示返回全部
        random_select (bool): 是否随机选择，默认为False
        
    Returns:
        list: 语义标签列表
    """
    try:
        # 构建基本查询
        query = SemanticLibrary.query.filter_by(category=category)
        
        # 应用随机排序
        if random_select:
            query = query.order_by(db.func.rand())
        
        # 应用限制
        if limit is not None:
            query = query.limit(limit)
            
        # 执行查询
        semantics = query.all()
        
        # 返回语义文本列表
        return [semantic.semantic_text for semantic in semantics]
        
    except Exception as e:
        current_app.logger.error(f"获取语义标签失败: {str(e)}")
        return []

def get_random_semantics_by_category(category, count=3):
    """
    随机获取指定类别的语义标签
    
    Args:
        category (str): 语义类别 ('subject', 'environment', 'behavior')
        count (int): 需要获取的标签数量
        
    Returns:
        list: 随机语义标签列表
    """
    return get_semantic_by_category(category, limit=count, random_select=True)

def get_all_semantics():
    """
    获取所有语义标签
    
    Returns:
        dict: 按类别分组的语义标签字典
    """
    try:
        result = {
            'subject': [],
            'environment': [],
            'behavior': [],
            'uncategorized': []
        }
        
        # 获取所有语义标签
        semantics = SemanticLibrary.query.all()
        
        # 按类别分组
        for semantic in semantics:
            if semantic.category == 'subject':
                result['subject'].append(semantic.semantic_text)
            elif semantic.category == 'environment':
                result['environment'].append(semantic.semantic_text)
            elif semantic.category == 'behavior':
                result['behavior'].append(semantic.semantic_text)
            else:
                result['uncategorized'].append(semantic.semantic_text)
                
        return result
        
    except Exception as e:
        current_app.logger.error(f"获取所有语义标签失败: {str(e)}")
        return {'subject': [], 'environment': [], 'behavior': [], 'uncategorized': []}

def search_semantics(query_text, category=None, limit=10):
    """
    搜索语义标签
    
    Args:
        query_text (str): 搜索关键词
        category (str, optional): 限制搜索的类别
        limit (int): 返回结果的最大数量
        
    Returns:
        list: 匹配的语义标签列表
    """
    try:
        # 构建基本查询
        query = SemanticLibrary.query.filter(
            SemanticLibrary.semantic_text.like(f"%{query_text}%")
        )
        
        # 如果指定了类别，则限制类别
        if category:
            query = query.filter_by(category=category)
            
        # 应用限制
        query = query.limit(limit)
        
        # 执行查询
        semantics = query.all()
        
        # 返回语义文本列表
        return [semantic.semantic_text for semantic in semantics]
        
    except Exception as e:
        current_app.logger.error(f"搜索语义标签失败: {str(e)}")
        return []

def get_semantic_stats():
    """
    获取语义库统计信息
    
    Returns:
        dict: 语义库统计信息
    """
    try:
        stats = {
            'total': SemanticLibrary.query.count(),
            'subject': SemanticLibrary.query.filter_by(category='subject').count(),
            'environment': SemanticLibrary.query.filter_by(category='environment').count(),
            'behavior': SemanticLibrary.query.filter_by(category='behavior').count(),
            'uncategorized': SemanticLibrary.query.filter_by(category=None).count()
        }
        return stats
        
    except Exception as e:
        current_app.logger.error(f"获取语义库统计信息失败: {str(e)}")
        return {'total': 0, 'subject': 0, 'environment': 0, 'behavior': 0, 'uncategorized': 0} 