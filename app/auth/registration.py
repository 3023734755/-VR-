from flask import current_app, session
from app import db
from app.models.models import User, SemanticLibrary, SemanticPassword, CompanionSemantic
from app.utils.semantic_utils import get_random_semantics_by_category
from app.semantic.story_generator import generate_stories_from_keywords
from app.semantic.semantic_labeler import extract_labels_from_text
import random
from sqlalchemy.exc import IntegrityError


def check_username_exists(username):

    return User.query.filter_by(username=username).first() is not None


def create_user(username):
    try:
        # 检查用户名是否已存在
        if check_username_exists(username):
            return None, "用户名已存在"
        
        # 创建新用户
        user = User(username=username)
        db.session.add(user)
        db.session.commit()
        
        current_app.logger.info(f"用户 {username} (ID: {user.id}) 注册成功")
        return user, None
    
    except IntegrityError:
        db.session.rollback()
        current_app.logger.error(f"创建用户时发生完整性错误: {username}")
        return None, "用户名已存在"
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"创建用户时出错: {str(e)}")
        return None, f"创建用户时出错: {str(e)}"


def get_semantic_candidates_for_registration():
    try:
        # 从每个类别中随机选择30个语义
        count = current_app.config.get('SEMANTIC_CANDIDATES_COUNT', 30)
        
        subject_semantics = get_random_semantics_by_category('subject', count)
        environment_semantics = get_random_semantics_by_category('environment', count)
        behavior_semantics = get_random_semantics_by_category('behavior', count)
        
        return {
            'subject': subject_semantics,
            'environment': environment_semantics,
            'behavior': behavior_semantics
        }
    
    except Exception as e:
        current_app.logger.error(f"获取语义候选项时出错: {str(e)}")
        return {'subject': [], 'environment': [], 'behavior': []}


def generate_stories_from_selected_keywords(keywords):
    """
    根据用户选择的关键词生成故事
    """
    try:
        # 生成3个故事
        num_stories = current_app.config.get('STORIES_COUNT', 3)
        stories = generate_stories_from_keywords(keywords, num_stories)
        
        return stories
    
    except Exception as e:
        current_app.logger.error(f"生成故事时出错: {str(e)}")
        return []


def extract_semantic_labels_from_story(story_text):
    """
    从故事文本中提取语义标签

    """
    try:
        # 每个类别提取3个标签
        num_per_category = current_app.config.get('SEMANTIC_LABELS_PER_CATEGORY', 3)
        
        # 提取语义标签
        labels = extract_labels_from_text(story_text, num_per_category)
        
        return labels
    
    except Exception as e:
        current_app.logger.error(f"提取语义标签时出错: {str(e)}")
        return {
            "subject_labels": [],
            "environment_labels": [],
            "behavior_labels": []
        }


def save_semantic_password(user_id, selected_semantics):
    """
    保存用户的语义密码

    """
    try:
        # 检查用户是否存在
        user = User.query.get(user_id)
        if not user:
            return False, "用户不存在"
        
        # 检查用户是否已设置语义密码
        if SemanticPassword.query.filter_by(user_id=user_id).first():
            return False, "该用户已设置语义密码，不能重复设置"
        
        # 检查语义数量
        required_count = current_app.config.get('SEMANTIC_COUNT', 3)
        if len(selected_semantics) != required_count:
            return False, f"需要选择{required_count}个语义密码"
        
        # 获取语义库中的所有语义，用于选择伴生语义
        all_semantics_by_category = {
            'subject': SemanticLibrary.query.filter_by(category='subject').all(),
            'environment': SemanticLibrary.query.filter_by(category='environment').all(),
            'behavior': SemanticLibrary.query.filter_by(category='behavior').all()
        }
        
        # 为每个选择的语义创建密码记录
        for position, semantic_info in enumerate(selected_semantics):
            semantic_text = semantic_info['text']
            category = semantic_info['category']
            
            # 查找或创建选择的语义
            semantic = SemanticLibrary.query.filter_by(semantic_text=semantic_text).first()
            if not semantic:
                semantic = SemanticLibrary(semantic_text=semantic_text, category=category)
                db.session.add(semantic)
                db.session.flush()
            
            # 创建语义密码记录
            semantic_password = SemanticPassword(
                user_id=user.id,
                semantic_id=semantic.id,
                position=position
            )
            db.session.add(semantic_password)
            db.session.flush()  # 获取语义密码ID
            
            # 为每个语义密码选择伴生语义
            # 从不同类别中选择伴生语义
            other_categories = []
            if category == 'subject':
                other_categories = ['environment', 'behavior']
            elif category == 'environment':
                other_categories = ['subject', 'behavior']
            elif category == 'behavior':
                other_categories = ['subject', 'environment']
            
            # 合并其他类别的语义
            available_semantics = []
            for other_category in other_categories:
                available_semantics.extend(all_semantics_by_category[other_category])
            
            # 确定伴生语义数量
            companion_count = current_app.config.get('COMPANION_SEMANTIC_COUNT', 17)
            if len(available_semantics) < companion_count:
                companion_count = len(available_semantics)
                current_app.logger.warning(f"可用的伴生语义不足{companion_count}个，只使用{companion_count}个")
            
            # 随机选择伴生语义
            companion_semantics = random.sample(available_semantics, companion_count)
            
            # 存储伴生语义
            for comp_position, comp_semantic in enumerate(companion_semantics):
                companion = CompanionSemantic(
                    semantic_password_id=semantic_password.id,
                    semantic_id=comp_semantic.id,
                    position=comp_position
                )
                db.session.add(companion)
        
        db.session.commit()
        
        current_app.logger.info(f"用户 ID: {user.id} 成功设置了 {len(selected_semantics)} 个语义密码和 {companion_count*len(selected_semantics)} 个伴生语义")
        
        return True, "语义密码设置成功"
    
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"语义密码设置错误(完整性约束): {str(e)}")
        return False, "该用户已设置语义密码或存在数据冲突"
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"语义密码设置错误: {str(e)}")
        return False, f"服务器处理请求时发生错误: {str(e)}" 