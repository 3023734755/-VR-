import os
from sqlalchemy import inspect
from app import db
from app.models.models import User, SemanticLibrary, SemanticPassword, CompanionSemantic
from flask import current_app

def check_tables_exist():
    inspector = inspect(db.engine)
    required_tables = [
        'users', 
        'semantic_library', 
        'semantic_passwords', 
        'companion_semantics',
        'auth_challenges',
        'auth_images'
    ]
    existing_tables = inspector.get_table_names()
    
    for table in required_tables:
        if table not in existing_tables:
            current_app.logger.info(f"表 {table} 不存在，需要创建")
            return False
    
    current_app.logger.info("所有必需的数据库表都已存在")
    return True

def create_tables():
    """
    创建所有必需的数据库表
    """
    try:
        current_app.logger.info("开始创建数据库表...")
        db.create_all()
        current_app.logger.info("数据库表创建成功")
        return True
    except Exception as e:
        current_app.logger.error(f"创建数据库表失败: {str(e)}")
        return False

def load_semantic_file(file_path, category):
    """
    从文件加载语义标签并按类别导入数据库
    """
    if not os.path.exists(file_path):
        current_app.logger.warning(f"语义文件不存在: {file_path}")
        return 0
        
    try:
        # 读取语义文件
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # 过滤有效行（非空且非注释行）
        semantics = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
        count = 0
        
        # 导入语义到数据库
        for semantic_text in semantics:
            # 检查是否已存在
            existing = SemanticLibrary.query.filter_by(semantic_text=semantic_text).first()
            if existing:
                # 如果存在但没有分类，则更新分类
                if not existing.category:
                    existing.category = category
                    count += 1
            else:
                # 不存在则创建新记录
                semantic = SemanticLibrary(semantic_text=semantic_text, category=category)
                db.session.add(semantic)
                count += 1
                
        # 提交更改
        db.session.commit()
        return count
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"导入语义文件失败 {file_path}: {str(e)}")
        return 0

def init_semantic_library():
    """
    初始化语义库，从语义词库文件导入基础语义
    """
    try:
        total_imported = 0
        base_dir = os.path.dirname(__file__)
        
        # 导入主体语义标签
        subject_file = os.path.join(base_dir, 'subject_semantics.txt')
        subject_count = load_semantic_file(subject_file, 'subject')
        current_app.logger.info(f"导入了 {subject_count} 个主体语义标签")
        total_imported += subject_count
        
        # 导入环境语义标签
        environment_file = os.path.join(base_dir, 'environment_semantics.txt')
        environment_count = load_semantic_file(environment_file, 'environment')
        current_app.logger.info(f"导入了 {environment_count} 个环境语义标签")
        total_imported += environment_count
        
        # 导入行为语义标签
        behavior_file = os.path.join(base_dir, 'behavior_semantics.txt')
        behavior_count = load_semantic_file(behavior_file, 'behavior')
        current_app.logger.info(f"导入了 {behavior_count} 个行为语义标签")
        total_imported += behavior_count
        
        # 如果没有导入任何新语义，尝试使用旧的语义文件
        if total_imported == 0:
            # 检查语义库是否已有数据
            if SemanticLibrary.query.count() > 0:
                current_app.logger.info("语义库已存在数据，跳过初始化")
                return True
                
            # 尝试使用旧的语义文件
            chinese_file_path = os.path.join(base_dir, 'chinese_semantics.txt')
            english_file_path = os.path.join(base_dir, 'seed_semantics.txt')
            
            if os.path.exists(chinese_file_path):
                chinese_count = load_semantic_file(chinese_file_path, None)
                current_app.logger.info(f"从旧文件导入了 {chinese_count} 个语义标签")
                total_imported += chinese_count
            elif os.path.exists(english_file_path):
                english_count = load_semantic_file(english_file_path, None)
                current_app.logger.info(f"从旧文件导入了 {english_count} 个语义标签")
                total_imported += english_count
        
        current_app.logger.info(f"总共导入 {total_imported} 个语义标签到数据库")
        return total_imported > 0
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"初始化语义库失败: {str(e)}")
        return False

def init_database():
    """
    初始化数据库，包括创建表和导入基础数据
    """
    try:
        # 检查表是否存在
        if not check_tables_exist():
            # 创建所有表
            if not create_tables():
                return False
        
        # 初始化语义库
        init_semantic_library()
        
        return True
    
    except Exception as e:
        current_app.logger.error(f"数据库初始化失败: {str(e)}")
        return False
