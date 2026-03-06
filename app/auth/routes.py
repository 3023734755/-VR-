from flask import request, jsonify, current_app, session, render_template
from sqlalchemy.exc import IntegrityError
from app import db
from app.auth import bp
from app.models.models import User, SemanticLibrary, SemanticPassword, CompanionSemantic
from app.models.auth_images import AuthImage
from app.utils.validators import validate_username, validate_selected_semantics
from app.utils.auth_image_utils import record_auth_images
from app.utils.http_utils import parse_request
from app.auth.registration import (
    check_username_exists, 
    create_user, 
    get_semantic_candidates_for_registration,
    generate_stories_from_selected_keywords,
    extract_semantic_labels_from_story,
    save_semantic_password
)
import random
import os
import uuid
import json
from datetime import datetime
from sqlalchemy.sql import func
import torch

@bp.route('/check_username', methods=['POST'])
def check_username():
    """检查用户名是否可用"""
    try:
        data = request.get_json()
        if not data:
            current_app.logger.warning(f"[API] 检查用户名失败: 无效的JSON数据 - IP: {request.remote_addr}")
            return jsonify({'error': '无效的JSON数据'}), 400
            
        username = data.get('username')
        current_app.logger.info(f"[API] 收到检查用户名请求: {username} - IP: {request.remote_addr}")
        
        # 验证用户名格式
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            current_app.logger.info(f"[API] 用户名格式无效: {username} - {error_msg}")
            return jsonify({'available': False, 'message': error_msg}), 200
        
        # 检查用户名是否已存在
        if check_username_exists(username):
            current_app.logger.info(f"[API] 用户名已存在: {username}")
            return jsonify({'available': False, 'message': '用户名已存在'}), 200
        
        current_app.logger.info(f"[API] 用户名可用: {username}")
        return jsonify({'available': True, 'message': '用户名可用'}), 200
        
    except Exception as e:
        current_app.logger.error(f"[API] 检查用户名接口异常: {str(e)}", exc_info=True)
        return jsonify({'error': f'服务器内部错误: {str(e)}'}), 500

@bp.route('/register', methods=['GET'])
def register_page():
    """显示注册页面"""
    return render_template('register.html')

@bp.route('/register', methods=['POST'])
def register():
    """注册新用户"""
    try:
        data = request.get_json()
        if not data:
            current_app.logger.warning(f"[API] 注册失败: 无效JSON - IP: {request.remote_addr}")
            return jsonify({'error': '无效的JSON数据'}), 400
            
        username = data.get('username')
        current_app.logger.info(f"[API] 收到注册请求: {username} - IP: {request.remote_addr}")
        
        # 验证用户名格式
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            current_app.logger.info(f"[API] 注册失败: 用户名格式无效 - {username}")
            return jsonify({'error': error_msg}), 400
        
        # 创建用户
        user, error = create_user(username)
        if error:
            current_app.logger.warning(f"[API] 注册失败: 创建用户错误 - {username}: {error}")
            return jsonify({'error': error}), 400
        
        # 将用户ID存入会话
        session['registration_user_id'] = user.id
        current_app.logger.info(f"[API] 用户注册成功: {username} (ID: {user.id})")
        
        return jsonify({
            'message': '用户创建成功',
            'user_id': user.id
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"[API] 注册接口异常: {str(e)}", exc_info=True)
        return jsonify({'error': f'服务器内部错误: {str(e)}'}), 500

@bp.route('/get_semantic_options', methods=['POST'])
def get_semantic_options():
    """获取语义选项
    从三类语义标签中各随机选择30个，供用户选择
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的JSON数据'}), 400
            
        user_id = data.get('user_id')
        
        # 验证用户ID
        if not user_id:
            return jsonify({'error': '用户ID是必需的'}), 400
        
        # 检查用户是否存在
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 检查会话中的用户ID是否匹配
        if session.get('registration_user_id') != user_id:
            return jsonify({'error': '会话已过期或无效'}), 401
        
        # 从三类语义标签中各随机选择30个
        subject_semantics = get_random_semantics('subject', 30)
        environment_semantics = get_random_semantics('environment', 30)
        behavior_semantics = get_random_semantics('behavior', 30)
        
        # 将语义候选存入会话
        session['registration_semantic_candidates'] = {
            'subject': subject_semantics,
            'environment': environment_semantics,
            'behavior': behavior_semantics
        }
        
        return jsonify({
            'message': '获取语义选项成功',
            'semantic_options': {
                'subject': subject_semantics,
                'environment': environment_semantics,
                'behavior': behavior_semantics
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"获取语义选项时出错: {str(e)}")
        return jsonify({'error': f'服务器处理请求时发生错误: {str(e)}'}), 500

@bp.route('/generate_stories', methods=['POST'])
def generate_stories():
    """生成语义故事
    接收用户选择的关键词，生成多个故事供用户选择
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的JSON数据'}), 400
            
        user_id = data.get('user_id')
        selected_keywords = data.get('selected_keywords')
        
        # 验证输入
        if not user_id:
            return jsonify({'error': '用户ID是必需的'}), 400
        if not selected_keywords:
            return jsonify({'error': '请选择关键词'}), 400
        
        # 验证关键词格式
        if not isinstance(selected_keywords, dict):
            return jsonify({'error': '关键词格式无效'}), 400
        if not all(key in selected_keywords for key in ['subject', 'environment', 'behavior']):
            return jsonify({'error': '请为每个类别选择关键词'}), 400
        
        # 检查用户是否存在
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 检查会话中的用户ID是否匹配
        if session.get('registration_user_id') != user_id:
            return jsonify({'error': '会话已过期或无效'}), 401
        
        # 生成3个不同的故事
        stories = []
        try:
            # 为每个故事组合不同的关键词
            for i in range(3):
                # 从每个类别选择的关键词中随机选一个
                subject_keyword = random.choice(selected_keywords['subject'])['text']
                environment_keyword = random.choice(selected_keywords['environment'])['text']
                behavior_keyword = random.choice(selected_keywords['behavior'])['text']
                
                story_keywords = [subject_keyword, environment_keyword, behavior_keyword]
                current_app.logger.info(f"故事{i+1}关键词: {story_keywords}")
                
                # 生成一个故事
                story = generate_story_with_keywords(story_keywords)
                if story:
                    stories.append(story)
                    current_app.logger.info(f"成功生成故事{i+1}, 长度: {len(story)}")
                else:
                    current_app.logger.warning(f"故事{i+1}生成失败")
        except Exception as e:
            current_app.logger.error(f"从选择的关键词生成故事时出错: {str(e)}")
            
            # 回退策略: 如果从选择的关键词生成失败，直接从文件中读取词汇
            try:
                current_app.logger.info("尝试从文件中直接读取语义关键词")
                # 读取语义文件
                base_dir = os.path.dirname(os.path.dirname(__file__))
                
                subject_file = os.path.join(base_dir, 'models', 'subject_semantics.txt')
                with open(subject_file, 'r', encoding='utf-8') as f:
                    subject_words = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                
                environment_file = os.path.join(base_dir, 'models', 'environment_semantics.txt')
                with open(environment_file, 'r', encoding='utf-8') as f:
                    environment_words = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                
                behavior_file = os.path.join(base_dir, 'models', 'behavior_semantics.txt')
                with open(behavior_file, 'r', encoding='utf-8') as f:
                    behavior_words = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                
                # 生成3个故事，每个故事从每个类别随机选择一个关键词
                for i in range(3):
                    subject_keyword = random.choice(subject_words[:50])  # 只从前50个词中选择
                    environment_keyword = random.choice(environment_words[:50])
                    behavior_keyword = random.choice(behavior_words[:50])
                    
                    story_keywords = [subject_keyword, environment_keyword, behavior_keyword]
                    story = generate_story_with_keywords(story_keywords)
                    if story:
                        stories.append(story)
            except Exception as inner_e:
                current_app.logger.error(f"从文件读取语义关键词并生成故事时出错: {str(inner_e)}")
                # 如果仍然失败，使用一些硬编码的关键词
                default_keywords = [
                    ["人类", "森林", "探险"],
                    ["科学家", "实验室", "研究"],
                    ["艺术家", "城市", "创作"]
                ]
                
                for keywords in default_keywords:
                    story = generate_story_with_template(keywords)
                    stories.append(story)
        
        # 确保至少有3个故事
        while len(stories) < 3:
            default_keywords = ["人物", "场景", "行为"]
            stories.append(generate_story_with_template(default_keywords))
            current_app.logger.warning(f"使用模板添加故事，当前故事数: {len(stories)}")
            
        # 将故事和语义候选存入会话
        session['registration_stories'] = stories
        session['registration_selected_keywords'] = selected_keywords
        
        current_app.logger.info(f"共生成 {len(stories)} 个故事")
        
        return jsonify({
            'message': '故事生成成功',
            'stories': stories
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"生成故事时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'服务器处理请求时发生错误: {str(e)}'}), 500

@bp.route('/select_story', methods=['POST'])
def select_story():
    """选择故事
    用户选择一个生成的故事
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的JSON数据'}), 400
            
        user_id = data.get('user_id')
        story_index = data.get('story_index')
        
        # 验证输入
        if not user_id:
            return jsonify({'error': '用户ID是必需的'}), 400
        if story_index is None:
            return jsonify({'error': '请选择故事'}), 400
        
        # 检查用户是否存在
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 检查会话中的用户ID是否匹配
        if session.get('registration_user_id') != user_id:
            return jsonify({'error': '会话已过期或无效'}), 401
        
        # 获取会话中的故事
        stories = session.get('registration_stories')
        if not stories or story_index >= len(stories):
            return jsonify({'error': '无效的故事选择'}), 400
        
        # 保存选择的故事
        selected_story = stories[story_index]
        session['registration_selected_story'] = selected_story
        
        return jsonify({
            'message': '故事选择成功',
            'selected_story': selected_story
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"选择故事时出错: {str(e)}")
        return jsonify({'error': f'服务器处理请求时发生错误: {str(e)}'}), 500

def get_random_semantics(category, count):
    """从指定类别中随机获取语义标签"""
    try:
        # 首先尝试从数据库中获取
        semantics = SemanticLibrary.query.filter_by(category=category).all()
        if semantics:
            if len(semantics) <= count:
                return [{'id': s.id, 'text': s.semantic_text} for s in semantics]
            
            # 随机选择指定数量的语义标签
            selected_semantics = random.sample(semantics, count)
            return [{'id': s.id, 'text': s.semantic_text} for s in selected_semantics]
        else:
            # 如果数据库中没有语义标签，从文件中读取
            current_app.logger.warning(f"数据库中未找到{category}类别的语义标签，尝试从文件中读取")
            return get_semantics_from_file(category, count)
    except Exception as e:
        # 如果从数据库获取失败，从文件中读取
        current_app.logger.error(f"从数据库获取语义标签失败: {str(e)}，尝试从文件中读取")
        return get_semantics_from_file(category, count)

def get_semantics_from_file(category, count):
    """从文件中读取语义标签"""
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        file_path = os.path.join(base_dir, 'models', f'{category}_semantics.txt')
        
        if not os.path.exists(file_path):
            current_app.logger.error(f"语义文件不存在: {file_path}")
            # 返回一些硬编码的默认值
            if category == 'subject':
                words = ["人", "男人", "女人", "孩子", "老人", "学生", "医生", "工人", "艺术家", "科学家"]
            elif category == 'environment':
                words = ["森林", "山脉", "草原", "沙漠", "海洋", "湖泊", "城市", "乡村", "公园", "学校"]
            elif category == 'behavior':
                words = ["走路", "跑步", "跳舞", "唱歌", "学习", "工作", "思考", "阅读", "交谈", "探索"]
            else:
                words = ["未知", "默认", "测试"]
            
            # 为每个词生成一个随机ID，确保ID不重复
            result = []
            for i, word in enumerate(words[:count]):
                result.append({'id': 10000 + i, 'text': word})
            return result
        
        # 读取语义文件
        with open(file_path, 'r', encoding='utf-8') as f:
            words = []
            for line in f:
                line = line.strip()
                # 跳过空行和注释行
                if line and not line.startswith('#'):
                    words.append(line)
        
        # 如果词汇数量少于请求数量，使用所有词汇
        if len(words) <= count:
            result = []
            for i, word in enumerate(words):
                result.append({'id': 10000 + i, 'text': word})
            return result
        
        # 随机选择指定数量的词汇
        selected_words = random.sample(words, count)
        result = []
        for i, word in enumerate(selected_words):
            result.append({'id': 10000 + i, 'text': word})
        
        return result
    except Exception as e:
        current_app.logger.error(f"从文件读取语义标签失败: {str(e)}")
        # 返回最少的几个词汇作为兜底
        if category == 'subject':
            default_words = ["人", "动物"]
        elif category == 'environment':
            default_words = ["森林", "城市"]
        elif category == 'behavior':
            default_words = ["走路", "说话"]
        else:
            default_words = ["未知"]
            
        result = []
        for i, word in enumerate(default_words):
            result.append({'id': 10000 + i, 'text': word})
        return result

def generate_story_with_keywords(keywords):
    """使用关键词生成故事"""
    try:
        # 导入故事生成器
        from app.semantic.story_generator import generate_stories_from_keywords
        
        current_app.logger.info(f"使用关键词生成故事: {keywords}")
        
        # 调用story_generator中的函数生成故事
        stories = generate_stories_from_keywords(keywords, num_stories=1)
        
        # 检查是否成功生成故事
        if stories and len(stories) > 0:
            # 返回第一个故事的内容
            story = stories[0]["story"]
            current_app.logger.info(f"生成的故事长度: {len(story)}字，前50字: {story[:50]}...")
            return story
        else:
            current_app.logger.warning("故事生成失败，使用模板方法")
            return generate_story_with_template(keywords)
            
    except Exception as e:
        current_app.logger.error(f"使用模型生成故事时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        # 出错时回退到模板方法
        return generate_story_with_template(keywords)

def generate_story_with_template(keywords):
    """使用模板生成故事（作为备份方法）"""
    # 简化的模板生成方法，仅在模型完全失效时使用
    story = f"""在{keywords[1]}中，一位{keywords[0]}正在{keywords[2]}。这是一个简短的故事，由于模型生成失败而使用备用模板创建。"""
    
    return story

@bp.route('/extract_labels', methods=['POST'])
def extract_labels():
    """从故事中提取语义标签
    """
    try:
        data = request.get_json()
        if not data:
            current_app.logger.error("接收到空的JSON数据")
            return jsonify({'error': '无效的JSON数据'}), 400
            
        user_id = data.get('user_id')
        
        # 验证输入
        if not user_id:
            current_app.logger.error("请求中缺少user_id")
            return jsonify({'error': '用户ID是必需的'}), 400
        
        # 检查用户是否存在
        user = User.query.get(user_id)
        if not user:
            current_app.logger.error(f"用户不存在: ID={user_id}")
            return jsonify({'error': '用户不存在'}), 404
        
        # 检查会话中的用户ID是否匹配
        if session.get('registration_user_id') != user_id:
            current_app.logger.error(f"会话中的用户ID {session.get('registration_user_id')} 与请求中的用户ID {user_id} 不匹配")
            return jsonify({'error': '会话已过期或无效'}), 401
        
        # 从会话中获取选择的故事
        selected_story = session.get('registration_selected_story')
        if not selected_story:
            current_app.logger.error(f"未找到选择的故事: 用户ID={user_id}")
            return jsonify({'error': '未找到选择的故事'}), 400
            
        # 从会话中获取语义候选
        candidates = session.get('registration_semantic_candidates')
        extracted_labels = {}
        
        try:
            # 使用BERT模型提取语义标签
            from app.semantic.semantic_labeler import extract_labels_from_text
            
            current_app.logger.info(f"从故事中提取语义标签: {selected_story[:100]}...")
            labels_per_category = current_app.config.get('SEMANTIC_LABELS_PER_CATEGORY', 3)
            
            # 使用语义标签提取器从故事中提取标签
            extracted_labels = extract_labels_from_text(selected_story, labels_per_category)
            current_app.logger.info(f"语义标签提取结果: {extracted_labels}")
            
            # 检查提取结果是否为空或者标签数量不足
            if (not extracted_labels or 
                not extracted_labels.get('subject_labels') or 
                not extracted_labels.get('environment_labels') or 
                not extracted_labels.get('behavior_labels')):
                raise ValueError("语义标签提取结果不完整")
                
            # 开始一个事务，确保所有数据库操作都是原子的
            db.session.begin_nested()  # 创建一个保存点
                
            # 确保每个标签都有有效的ID
            # 从数据库查找匹配的语义标签
            processed_labels = {
                'subject': [],
                'environment': [],
                'behavior': []
            }
            
            # 处理主体类别标签
            for label in extracted_labels.get('subject_labels', []):
                try:
                    # 在数据库中查找匹配的语义
                    semantic = SemanticLibrary.query.filter_by(
                        semantic_text=label,
                        category='subject'
                    ).first()
                    
                    if semantic:
                        # 如果找到匹配的语义，使用数据库中的ID
                        processed_labels['subject'].append({
                            'id': semantic.id,
                            'text': semantic.semantic_text
                        })
                        current_app.logger.debug(f"找到现有的主体语义: {semantic.semantic_text} (ID={semantic.id})")
                    else:
                        # 如果没有找到匹配的语义，创建一个新的
                        new_semantic = SemanticLibrary(
                            semantic_text=label,
                            category='subject'
                        )
                        db.session.add(new_semantic)
                        db.session.flush()  # 获取ID
                        
                        processed_labels['subject'].append({
                            'id': new_semantic.id,
                            'text': new_semantic.semantic_text
                        })
                        current_app.logger.info(f"创建新的主体语义: {new_semantic.semantic_text} (ID={new_semantic.id})")
                except Exception as e:
                    current_app.logger.error(f"处理主体语义标签时出错: {str(e)}")
                    db.session.rollback()
                    raise
            
            # 处理环境类别标签
            for label in extracted_labels.get('environment_labels', []):
                try:
                    semantic = SemanticLibrary.query.filter_by(
                        semantic_text=label,
                        category='environment'
                    ).first()
                    
                    if semantic:
                        processed_labels['environment'].append({
                            'id': semantic.id,
                            'text': semantic.semantic_text
                        })
                        current_app.logger.debug(f"找到现有的环境语义: {semantic.semantic_text} (ID={semantic.id})")
                    else:
                        new_semantic = SemanticLibrary(
                            semantic_text=label,
                            category='environment'
                        )
                        db.session.add(new_semantic)
                        db.session.flush()
                        
                        processed_labels['environment'].append({
                            'id': new_semantic.id,
                            'text': new_semantic.semantic_text
                        })
                        current_app.logger.info(f"创建新的环境语义: {new_semantic.semantic_text} (ID={new_semantic.id})")
                except Exception as e:
                    current_app.logger.error(f"处理环境语义标签时出错: {str(e)}")
                    db.session.rollback()
                    raise
            
            # 处理行为类别标签
            for label in extracted_labels.get('behavior_labels', []):
                try:
                    semantic = SemanticLibrary.query.filter_by(
                        semantic_text=label,
                        category='behavior'
                    ).first()
                    
                    if semantic:
                        processed_labels['behavior'].append({
                            'id': semantic.id,
                            'text': semantic.semantic_text
                        })
                        current_app.logger.debug(f"找到现有的行为语义: {semantic.semantic_text} (ID={semantic.id})")
                    else:
                        new_semantic = SemanticLibrary(
                            semantic_text=label,
                            category='behavior'
                        )
                        db.session.add(new_semantic)
                        db.session.flush()
                        
                        processed_labels['behavior'].append({
                            'id': new_semantic.id,
                            'text': new_semantic.semantic_text
                        })
                        current_app.logger.info(f"创建新的行为语义: {new_semantic.semantic_text} (ID={new_semantic.id})")
                except Exception as e:
                    current_app.logger.error(f"处理行为语义标签时出错: {str(e)}")
                    db.session.rollback()
                    raise
            
            # 提交新创建的语义标签
            db.session.commit()
            current_app.logger.info(f"成功保存所有语义标签")
            
            # 使用处理后的标签
            extracted_labels = processed_labels
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"使用BERT模型提取语义标签失败: {str(e)}")
            current_app.logger.info("尝试从候选项中随机选择语义标签...")
            
            # 如果使用BERT模型提取失败，尝试从候选项中随机选择
            if candidates:
                # 为每类标签随机选择3个作为提取结果
                extracted_labels = {
                    'subject': random.sample(candidates['subject'], min(3, len(candidates['subject']))),
                    'environment': random.sample(candidates['environment'], min(3, len(candidates['environment']))),
                    'behavior': random.sample(candidates['behavior'], min(3, len(candidates['behavior'])))
                }
                current_app.logger.info(f"从候选项中随机选择了语义标签: {len(extracted_labels['subject'])} 个主体, {len(extracted_labels['environment'])} 个环境, {len(extracted_labels['behavior'])} 个行为")
            else:
                # 如果没有候选项，从文件中直接读取
                current_app.logger.warning("会话中未找到语义候选项，尝试从文件中读取")
                extracted_labels = {
                    'subject': get_semantics_from_file('subject', 3),
                    'environment': get_semantics_from_file('environment', 3),
                    'behavior': get_semantics_from_file('behavior', 3)
                }
                current_app.logger.info(f"从文件中读取了语义标签: {len(extracted_labels['subject'])} 个主体, {len(extracted_labels['environment'])} 个环境, {len(extracted_labels['behavior'])} 个行为")
        
        # 将提取的标签存入会话
        session['registration_extracted_labels'] = extracted_labels
        
        # 打印最终的标签数据，确保格式正确
        current_app.logger.info(f"最终返回的语义标签: {json.dumps(extracted_labels, ensure_ascii=False)}")
        
        return jsonify({
            'message': '语义标签提取成功',
            'labels': extracted_labels
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"提取语义标签时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'服务器处理请求时发生错误: {str(e)}'}), 500

@bp.route('/select_semantics', methods=['POST'])
def select_semantics():
    """用户选择语义密码"""
    try:
        data = request.get_json()
        if not data:
            current_app.logger.error("接收到空的JSON数据")
            return jsonify({'error': '无效的JSON数据'}), 400
            
        # 详细记录接收到的数据（注意移除敏感信息）
        current_app.logger.info(f"接收到的select_semantics数据: {json.dumps(data, ensure_ascii=False)}")
            
        user_id = data.get('user_id')
        selected_semantics = data.get('selected_semantics')
        
        # 验证输入
        if not user_id:
            current_app.logger.error("请求中缺少user_id")
            return jsonify({'error': '用户ID是必需的'}), 400
        
        if not selected_semantics:
            current_app.logger.error(f"用户ID {user_id} 的请求中缺少selected_semantics")
            return jsonify({'error': '请选择语义密码'}), 400
            
        if not isinstance(selected_semantics, list):
            current_app.logger.error(f"用户ID {user_id} 的selected_semantics不是列表，而是 {type(selected_semantics)}")
            return jsonify({'error': 'selected_semantics必须是列表'}), 400
            
        if len(selected_semantics) != 3:
            current_app.logger.error(f"用户ID {user_id} 的selected_semantics长度不是3，而是 {len(selected_semantics)}")
            return jsonify({'error': '请选择3个语义密码（每个类别1个）'}), 400
        
        # 检查每个语义是否包含必要的字段
        for i, item in enumerate(selected_semantics):
            if not isinstance(item, dict):
                current_app.logger.error(f"用户ID {user_id} 的selected_semantics[{i}]不是字典，而是 {type(item)}")
                return jsonify({'error': f'语义密码 #{i+1} 格式无效'}), 400
                
            if 'position' not in item:
                current_app.logger.error(f"用户ID {user_id} 的selected_semantics[{i}]缺少position")
                return jsonify({'error': f'语义密码 #{i+1} 缺少位置信息'}), 400
                
            if 'semantic_id' not in item:
                current_app.logger.error(f"用户ID {user_id} 的selected_semantics[{i}]缺少semantic_id")
                return jsonify({'error': f'语义密码 #{i+1} 缺少语义ID'}), 400
                
            if item.get('semantic_id') is None:
                current_app.logger.error(f"用户ID {user_id} 的selected_semantics[{i}]的semantic_id为None")
                return jsonify({'error': f'语义密码 #{i+1} 的语义ID不能为空'}), 400
        
        # 检查用户是否存在
        user = User.query.get(user_id)
        if not user:
            current_app.logger.error(f"用户不存在: ID={user_id}")
            return jsonify({'error': '用户不存在'}), 404
        
        # 检查会话中的用户ID是否匹配
        if session.get('registration_user_id') != user_id:
            current_app.logger.error(f"会话中的用户ID {session.get('registration_user_id')} 与请求中的用户ID {user_id} 不匹配")
            return jsonify({'error': '会话已过期或无效'}), 401
        
        # 检查是否已经设置过语义密码
        existing_passwords = SemanticPassword.query.filter_by(user_id=user_id).count()
        if existing_passwords > 0:
            current_app.logger.warning(f"用户 {user.username} (ID: {user_id}) 已经设置过语义密码，数量: {existing_passwords}")
        current_app.logger.info(f"开始为用户 {user.username} (ID: {user_id}) 设置语义密码")
        for i, item in enumerate(selected_semantics):
            current_app.logger.info(f"语义密码 #{i+1}: position={item.get('position')}, semantic_id={item.get('semantic_id')}")
        
        # 保存语义密码
        images_generated = 0
        semantics_count = 0
        semantic_passwords_created = []
        
        try:
            db.session.begin_nested()
            # 第一阶段：创建语义密码和伴生语义
            for item in selected_semantics:
                position = item.get('position')
                semantic_id = item.get('semantic_id')
                if position is None or semantic_id is None:
                    current_app.logger.warning(f"跳过无效的语义数据: position={position}, semantic_id={semantic_id}")
                    continue
                
                # 获取语义标签
                semantic = SemanticLibrary.query.get(semantic_id)
                if not semantic:
                    current_app.logger.warning(f"找不到语义ID: {semantic_id}")
                    db.session.rollback()
                    return jsonify({'error': f'找不到语义ID: {semantic_id}'}), 404
                
                current_app.logger.info(f"处理位置 {position} 的语义: {semantic.semantic_text} (ID: {semantic_id})")

                existing_password = SemanticPassword.query.filter_by(
                    user_id=user_id,
                    position=position
                ).first()
                
                if existing_password:
                    current_app.logger.warning(f"用户 {user.username} 在位置 {position} 已存在语义密码，将被替换")
                    CompanionSemantic.query.filter_by(semantic_password_id=existing_password.id).delete()
                    db.session.delete(existing_password)
                
                # 创建语义密码
                semantic_password = SemanticPassword(
                    user_id=user_id,
                    semantic_id=semantic_id,
                    position=position,
                    created_on=datetime.now()
                )
                db.session.add(semantic_password)
                db.session.flush()  # 获取ID
                semantics_count += 1
                semantic_passwords_created.append(semantic_password)
                current_app.logger.info(f"创建语义密码: ID={semantic_password.id}, 位置={position}")
                
                # 为每个语义密码选择17个随机的伴生语义（不同类别的标签）
                category = semantic.category
                companion_semantics = SemanticLibrary.query.filter(
                    SemanticLibrary.category != category
                ).order_by(func.random()).limit(17).all()
                
                if not companion_semantics or len(companion_semantics) == 0:
                    current_app.logger.error(f"找不到类别 {category} 以外的语义标签作为伴生语义")
                    db.session.rollback()
                    return jsonify({'error': f'找不到足够的伴生语义'}), 500
                
                current_app.logger.info(f"为语义密码 {semantic_password.id} 选择了 {len(companion_semantics)} 个伴生语义")
                
                # 保存伴生语义
                try:
                    for pos, comp_semantic in enumerate(companion_semantics):
                        companion = CompanionSemantic(
                            semantic_password_id=semantic_password.id,  # 使用正确的字段名
                            semantic_id=comp_semantic.id,
                            position=pos  # 添加位置信息
                        )
                        db.session.add(companion)
                    current_app.logger.info(f"为语义密码 {semantic_password.id} 添加了 {len(companion_semantics)} 个伴生语义")
                except Exception as e:
                    current_app.logger.error(f"添加伴生语义时出错: {str(e)}")
                    db.session.rollback()
                    return jsonify({'error': f'添加伴生语义时出错: {str(e)}'}), 500

            db.session.commit()
            current_app.logger.info(f"成功保存用户 {user.username} 的 {semantics_count} 个语义密码和伴生语义")
            
            # 第二阶段：生成认证图片
            try:
                for semantic_password in semantic_passwords_created:
                    position = semantic_password.position
                    semantic_id = semantic_password.semantic_id
                    
                    current_app.logger.info(f"开始为位置 {position} 生成认证图片")
                    generated_count = generate_auth_images(user_id, semantic_id, position)
                    current_app.logger.info(f"位置 {position} 生成了 {generated_count} 张图片")
                    
                    # 如果没有生成图片，记录警告但继续处理
                    if generated_count == 0:
                        current_app.logger.warning(f"位置 {position} 没有生成任何图片，但语义密码已保存")
                    
                    images_generated += generated_count
                
                # 提交所有更改，包括图片记录
                db.session.commit()
                current_app.logger.info(f"用户 {user.username} 的语义密码设置成功: {semantics_count} 个密码, {images_generated} 张图片")
            except Exception as e:
                current_app.logger.error(f"生成认证图片时出错: {str(e)}")
                db.session.rollback()
                # 不返回错误，因为语义密码已经成功保存
                
            # 清除会话中的注册数据
            session.pop('registration_user_id', None)
            session.pop('registration_stories', None)
            session.pop('registration_selected_story', None)
            session.pop('registration_semantic_candidates', None)
            session.pop('registration_extracted_labels', None)
            session.pop('registration_selected_keywords', None)
            
            return jsonify({
                'message': '语义密码设置成功',
                'user_id': user_id,
                'semantics_count': semantics_count,
                'images_generated': images_generated
            }), 200
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"设置语义密码过程中出错: {str(e)}")
            import traceback
            current_app.logger.error(traceback.format_exc())
            return jsonify({'error': f'设置语义密码过程中出错: {str(e)}'}), 500
            
    except Exception as e:
        current_app.logger.error(f"设置语义密码时出错: {str(e)}")
        return jsonify({'error': f'服务器处理请求时发生错误: {str(e)}'}), 500

def generate_auth_images(user_id, semantic_id, position):
    """生成认证图片
    """
    try:
        # 获取用户信息
        user = User.query.get(user_id)
        if not user:
            current_app.logger.error(f"用户不存在: ID={user_id}")
            return 0
            
        # 获取语义密码信息
        semantic = SemanticLibrary.query.get(semantic_id)
        if not semantic:
            current_app.logger.error(f"语义不存在: ID={semantic_id}")
            return 0
            
        # 获取语义密码的伴生语义
        semantic_password = SemanticPassword.query.filter_by(
            user_id=user_id,
            semantic_id=semantic_id,
            position=position
        ).first()
        
        if not semantic_password:
            current_app.logger.error(f"语义密码不存在: 用户ID={user_id}, 语义ID={semantic_id}, 位置={position}")
            return 0
            
        # 获取伴生语义
        companion_semantics = CompanionSemantic.query.filter_by(
            semantic_password_id=semantic_password.id
        ).all()
        
        if not companion_semantics or len(companion_semantics) == 0:
            current_app.logger.error(f"未找到伴生语义: 密码ID={semantic_password.id}")
            return 0
            
        current_app.logger.info(f"获取到 {len(companion_semantics)} 个伴生语义")
        
        # 创建用户图像目录
        try:
            user_images_dir = os.path.join(current_app.config['USER_IMAGES_FOLDER'], user.username)
            os.makedirs(user_images_dir, exist_ok=True)
            
            # 创建位置目录 - 注意：在文件系统路径中，我们使用position_N而不是position_0，以避免混淆
            position_dir = os.path.join(user_images_dir, f"position_{position}")
            os.makedirs(position_dir, exist_ok=True)
            
            current_app.logger.info(f"创建用户图像目录: {position_dir}")
        except Exception as e:
            current_app.logger.error(f"创建图像目录时出错: {str(e)}")
            return 0
        
        # 初始化在线图片生成器
        try:
            from app.utils.image_generation.online_generator import OnlineImageGenerator
            online_generator = OnlineImageGenerator()
        except Exception as e:
            current_app.logger.error(f"初始化图片生成器时出错: {str(e)}")
            return 0
        
        # 获取伴生语义对象
        companion_semantics_objects = []
        for cs in companion_semantics:
            comp_semantic = SemanticLibrary.query.get(cs.semantic_id)
            if comp_semantic:
                companion_semantics_objects.append(comp_semantic)
        
        # 确保有足够的伴生语义
        if len(companion_semantics_objects) < 8:
            current_app.logger.warning(f"伴生语义数量不足8个，只有{len(companion_semantics_objects)}个")
            # 如果伴生语义不足，从其他类别中随机选择一些语义补充
            other_semantics = SemanticLibrary.query.filter(
                SemanticLibrary.category != semantic.category,
                SemanticLibrary.id != semantic_id
            ).order_by(func.random()).limit(8 - len(companion_semantics_objects)).all()
            
            companion_semantics_objects.extend(other_semantics)
            current_app.logger.info(f"补充了 {len(other_semantics)} 个伴生语义，总数: {len(companion_semantics_objects)}")

        selected_companions = random.sample(companion_semantics_objects, min(8, len(companion_semantics_objects)))
        current_app.logger.info(f"选择了 {len(selected_companions)} 个伴生语义用于生成干扰图片")
        password_image_path = os.path.join(position_dir, f"password_1.jpg")
        password_prompt = semantic.semantic_text
        enhanced_password_prompt = f"清晰可见的{password_prompt}，高质量照片，细节丰富"
        current_app.logger.info(f"生成密码图片: {enhanced_password_prompt} -> {password_image_path}")
        
        images_count = 0

        try:
            success, result = online_generator.generate_semantic_authentication_image(enhanced_password_prompt, password_image_path)
            
            if success:
                # 记录到数据库 - 明确标记为密码图片
                auth_image = AuthImage(
                    user_id=user_id,
                    position=position,  # 使用原始position值，可能是0
                    image_path=password_image_path,
                    semantic1_id=semantic_id,
                    is_password_image=True,  # 明确标记为密码图片
                    created_on=datetime.now()  # 添加创建时间
                )
                db.session.add(auth_image)
                db.session.flush()  # 立即获取ID，不提交事务
                
                current_app.logger.info(f"密码图片生成成功: ID={auth_image.id}, 路径={password_image_path}")
                images_count += 1
            else:
                current_app.logger.error(f"密码图片生成失败: {result}")
        except Exception as e:
            current_app.logger.error(f"生成密码图片时出错: {str(e)}")
            import traceback
            current_app.logger.error(traceback.format_exc())
        
        # 生成8张干扰图片，每张使用一个伴生语义与另一个随机伴生语义的组合
        for i, companion in enumerate(selected_companions):
            try:
                # 从剩余的伴生语义中随机选择一个，形成组合
                remaining_companions = [c for c in selected_companions if c.id != companion.id]
                if remaining_companions:
                    second_companion = random.choice(remaining_companions)
                    
                    # 构建组合提示词 - 确保与密码语义有足够区别
                    combined_prompt = f"{companion.semantic_text}和{second_companion.semantic_text}"
                    
                    # 生成图片
                    distractor_path = os.path.join(position_dir, f"distractor_{i+1}.jpg")
                    current_app.logger.info(f"生成干扰图片: {combined_prompt} -> {distractor_path}")
                    
                    success, result = online_generator.generate_semantic_authentication_image(combined_prompt, distractor_path)
                    
                    if success:
                        auth_image = AuthImage(
                            user_id=user_id,
                            position=position,
                            image_path=distractor_path,
                            semantic1_id=companion.id,
                            semantic2_id=second_companion.id,
                            is_password_image=False,  # 明确标记为非密码图片
                            created_on=datetime.now()  # 添加创建时间
                        )
                        db.session.add(auth_image)
                        db.session.flush()  # 立即获取ID，不提交事务
                        
                        current_app.logger.info(f"干扰图片生成成功: ID={auth_image.id}, 路径={distractor_path}")
                        images_count += 1
                    else:
                        current_app.logger.error(f"干扰图片生成失败: {result}")
            except Exception as e:
                current_app.logger.error(f"生成干扰图片时出错: {str(e)}")
                import traceback
                current_app.logger.error(traceback.format_exc())
                # 继续处理下一张图片
                continue
        
        # 验证是否成功生成了足够的图片
        if images_count < 9:
            current_app.logger.warning(f"位置 {position} 的图片生成不完整，只生成了 {images_count}/9 张图片")
        else:
            current_app.logger.info(f"为用户 {user.username} 在位置 {position} 成功生成了全部 {images_count} 张图片")
        
        # 检查是否至少有一张密码图片
        password_images = AuthImage.query.filter_by(
            user_id=user_id,
            position=position,
            is_password_image=True
        ).all()
        
        if not password_images:
            current_app.logger.error(f"位置 {position} 没有生成任何密码图片，认证将无法进行")
        
        return images_count
            
    except Exception as e:
        current_app.logger.error(f"生成认证图片时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        # 不回滚事务，让外层函数决定是否回滚
        return 0

# 登录认证流程
@bp.route('/login/challenge', methods=['POST'])
def login_challenge():
    """
    用户登录的第一阶段 - 输入用户名，服务器返回认证挑战
    
    流程：
    1. 用户提供用户名
    2. 服务器验证用户名是否存在
    3. 如存在，生成一个认证挑战票据，包含：
       - username: 用户名
       - challenge_id: 随机唯一标识
       - nonce: 一次性随机数
       - timestamp: 当前时间戳
       - server_signature: 服务器对challenge_id的签名
    """
    try:
        # 获取请求数据
        if not request.is_json:
            current_app.logger.warning("登录请求不是JSON格式")
            return jsonify({'error': '请求必须是JSON格式'}), 400
        
        data = request.get_json()
        if not data:
            current_app.logger.warning("登录请求包含无效的JSON数据")
            return jsonify({'error': '无效的JSON数据'}), 400
        
        username = data.get('username')
        if not username:
            current_app.logger.warning("登录请求缺少用户名")
            return jsonify({'error': '用户名是必需的'}), 400
        
        current_app.logger.info(f"接收到用户 {username} 的登录请求")
        
        # 验证用户名格式
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            current_app.logger.warning(f"用户名 {username} 格式无效: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # 检查用户是否存在
        user = User.query.filter_by(username=username).first()
        if not user:
            # 出于安全考虑，不直接告知用户不存在，使用通用错误
            current_app.logger.warning(f"用户名 {username} 不存在")
            return jsonify({'error': '用户名或密码错误'}), 401
        
        current_app.logger.info(f"用户 {username} (ID={user.id}) 存在，准备生成认证挑战")
        
        # 获取服务器签名密钥
        server_secret_key = current_app.config.get('SERVER_SIGNATURE_KEY')
        if not server_secret_key:
            current_app.logger.error("服务器签名密钥未配置")
            return jsonify({'error': '服务器配置错误'}), 500
        
        # 检查用户是否已经设置了语义密码
        semantic_passwords = SemanticPassword.query.filter_by(user_id=user.id).all()
        if not semantic_passwords:
            current_app.logger.warning(f"用户 {username} 尚未设置语义密码")
            return jsonify({'error': '用户尚未完成注册流程，请先设置语义密码'}), 400
        
        # 检查用户是否有认证图片
        auth_images = AuthImage.query.filter_by(user_id=user.id).all()
        if not auth_images:
            current_app.logger.warning(f"用户 {username} 没有认证图片")
            return jsonify({'error': '用户认证图片未生成，请联系管理员'}), 400
        
        # 创建认证挑战
        from app.models.auth_challenge import AuthChallenge
        challenge = AuthChallenge.create_challenge(user.id, server_secret_key)
        
        # 返回挑战数据
        response_data = challenge.to_dict()
        
        current_app.logger.info(f"为用户 {username} 生成登录挑战: {challenge.challenge_id}")
        return jsonify(response_data), 200
    
    except Exception as e:
        current_app.logger.error(f"生成登录挑战时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'服务器处理请求时发生错误: {str(e)}'}), 500

@bp.route('/login/images/<string:challenge_id>/<int:position>', methods=['GET'])
def get_login_images(challenge_id, position):
    """获取登录认证图片
    
    返回指定位置的认证图片，包括正确的语义密码图片和干扰图片
    
    注意：前端传入的position从1开始，数据库中的position从0开始
    """
    try:
        current_app.logger.info(f"获取登录图片: 挑战ID={challenge_id}, 位置={position}")
        
        # 验证挑战ID
        from app.models.auth_challenge import AuthChallenge
        challenge = AuthChallenge.query.filter_by(challenge_id=challenge_id).first()
        
        if not challenge:
            current_app.logger.warning(f"无效的挑战ID: {challenge_id}")
            return jsonify({'error': '无效的挑战ID'}), 400
            
        if not challenge.is_valid():
            current_app.logger.warning(f"挑战已过期或已使用: {challenge_id}")
            return jsonify({'error': '挑战已过期或已使用'}), 400
        
        # 获取用户
        user = User.query.get(challenge.user_id)
        if not user:
            current_app.logger.warning(f"用户不存在: ID={challenge.user_id}")
            return jsonify({'error': '用户不存在'}), 404
        
        current_app.logger.info(f"为用户 {user.username} (ID={user.id}) 获取位置 {position} 的认证图片")
        
        # 获取指定位置的语义密码
        # 注意：前端传入的position从1开始，数据库中的position从0开始
        db_position = position - 1
        
        semantic_password = SemanticPassword.query.filter_by(
            user_id=user.id,
            position=db_position
        ).first()
        
        if not semantic_password:
            current_app.logger.warning(f"用户 {user.username} 在位置 {position}(数据库位置:{db_position}) 没有语义密码")
            return jsonify({'error': f'用户在位置{position}没有语义密码'}), 404
        
        # 获取该位置的认证图片
        auth_images = AuthImage.get_random_images_for_position(user.id, db_position, 9)
        
        if not auth_images:
            current_app.logger.warning(f"用户 {user.username} 在位置 {position}(数据库位置:{db_position}) 没有认证图片")
            return jsonify({'error': f'用户在位置{position}没有认证图片'}), 404
        
        current_app.logger.info(f"获取到 {len(auth_images)} 张认证图片")
        
        # 构建响应
        images_data = []
        for img in auth_images:
            # 使用AuthImage模型的get_image_url方法获取URL
            images_data.append({
                'id': img.id,
                'url': img.get_image_url(),
                'position': position
            })
        
        # 随机排序图片
        random.shuffle(images_data)
        
        # 记录是否包含正确图片的信息（仅日志用途）
        correct_images = [img for img in auth_images if img.is_password_image]
        current_app.logger.info(f"返回的图片中包含 {len(correct_images)} 张正确的密码图片")
        
        return jsonify({
            'challenge_id': challenge_id,
            'position': position,
            'images_count': len(images_data),
            'images': images_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"获取登录图片时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'服务器处理请求时发生错误: {str(e)}'}), 500

@bp.route('/login/verify', methods=['POST'])
def verify_login():
    """验证登录选择的图片
    验证用户选择的图片是否包含正确的语义密码
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的JSON数据'}), 400
            
        challenge_id = data.get('challenge_id')
        position = data.get('position')
        image_id = data.get('image_id')
        
        # 验证输入
        if not challenge_id:
            return jsonify({'error': '挑战ID是必需的'}), 400
        if position is None:  # 修改验证逻辑，确保position=0不会被跳过
            return jsonify({'error': '位置是必需的'}), 400
        if not image_id:
            return jsonify({'error': '图片ID是必需的'}), 400
        
        current_app.logger.info(f"验证登录: 挑战ID={challenge_id}, 位置={position}, 图片ID={image_id}")
        
        # 验证挑战ID
        from app.models.auth_challenge import AuthChallenge
        challenge = AuthChallenge.query.filter_by(challenge_id=challenge_id).first()
        
        if not challenge:
            current_app.logger.warning(f"无效的挑战ID: {challenge_id}")
            return jsonify({'error': '无效的挑战ID'}), 400
            
        if not challenge.is_valid():
            current_app.logger.warning(f"挑战已过期或已使用: {challenge_id}")
            return jsonify({'error': '挑战已过期或已使用'}), 400
        
        # 获取用户
        user = User.query.get(challenge.user_id)
        if not user:
            current_app.logger.warning(f"用户不存在: ID={challenge.user_id}")
            return jsonify({'error': '用户不存在'}), 404
        
        current_app.logger.info(f"验证用户 {user.username} (ID={user.id}) 在位置 {position} 的选择")
        
        # 验证图片选择
        auth_image = AuthImage.query.get(image_id)
        if not auth_image:
            current_app.logger.warning(f"无效的图片ID: {image_id}")
            return jsonify({'error': '无效的图片ID'}), 400
            
        if auth_image.user_id != user.id:
            current_app.logger.warning(f"图片不属于该用户: 图片用户ID={auth_image.user_id}, 当前用户ID={user.id}")
            return jsonify({'error': '图片不属于该用户'}), 403
        
        # 注意：前端传入的position从1开始，数据库中的position从0开始
        db_position = position - 1
            
        if auth_image.position != db_position:
            current_app.logger.warning(f"图片位置不匹配: 图片位置={auth_image.position}, 请求位置={db_position}")
            return jsonify({'error': '图片位置不匹配'}), 400
        
        # 检查是否是正确的语义密码图片
        if not auth_image.is_password_image:
            # 验证失败，标记挑战为已使用
            challenge.mark_used()
            db.session.commit()
            
            current_app.logger.warning(f"用户 {user.username} 在位置 {position}(数据库位置:{db_position}) 选择了错误的图片")
            
            # 获取正确的图片信息，用于日志记录
            correct_image = AuthImage.query.filter_by(
                user_id=user.id,
                position=db_position,
                is_password_image=True
            ).first()
            
            if correct_image:
                semantic_info = correct_image.get_semantic_info()
                current_app.logger.info(f"正确图片的语义信息: {semantic_info}")
            
            return jsonify({
                'success': False,
                'message': '验证失败，请重新登录'
            }), 401
        
        # 如果是最后一个位置，则登录成功
        semantic_count = current_app.config.get('SEMANTIC_COUNT', 3)
        if position == semantic_count:
            # 验证成功，标记挑战为已使用
            challenge.mark_used()
            db.session.commit()
            
            # 生成会话令牌
            session['user_id'] = user.id
            session['username'] = user.username
            session['login_time'] = datetime.utcnow().isoformat()
            
            current_app.logger.info(f"用户 {user.username} 登录成功")
            
            return jsonify({
                'success': True,
                'message': '登录成功',
                'user_id': user.id,
                'username': user.username,
                'completed': True
            }), 200
        else:
            # 还有更多位置需要验证
            current_app.logger.info(f"用户 {user.username} 在位置 {position}(数据库位置:{db_position}) 验证成功，继续下一个位置")
            
            return jsonify({
                'success': True,
                'message': '验证成功，请继续选择下一个位置的语义密码',
                'next_position': position + 1,
                'completed': False
            }), 200
            
    except Exception as e:
        current_app.logger.error(f"验证登录时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'服务器处理请求时发生错误: {str(e)}'}), 500
