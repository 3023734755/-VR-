from flask import request, jsonify, current_app, session
from app import db
from app.user import bp
from app.models.models import User, SemanticPassword, CompanionSemantic, SemanticLibrary
from app.auth.routes import validate_username
from datetime import datetime
import random

@bp.route('/profile/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    """获取用户信息
    
    返回用户的基本信息，不包括语义密码
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    # 查询用户是否已设置语义密码
    has_semantics = SemanticPassword.query.filter_by(user_id=user_id).count() > 0
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'registered_on': user.registered_on.isoformat(),
        'has_set_semantics': has_semantics
    }), 200

@bp.route('/profile/<int:user_id>', methods=['PUT'])
def update_user_profile(user_id):
    """更新用户信息
    
    允许用户更新非敏感信息，如用户名
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    data = request.get_json()
    new_username = data.get('username')
    
    if new_username:
        # 验证用户名
        is_valid, error_msg = validate_username(new_username)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=new_username).first() and new_username != user.username:
            return jsonify({'error': '用户名已存在'}), 409
        
        user.username = new_username
        db.session.commit()
    
    return jsonify({
        'message': '用户信息更新成功',
        'user': {
            'id': user.id,
            'username': user.username,
            'registered_on': user.registered_on.isoformat()
        }
    }), 200

@bp.route('/all', methods=['GET'])
def get_all_users():
    """获取所有用户列表
    
    仅返回用户ID和用户名，主要用于管理员功能
    """
    users = User.query.all()
    return jsonify({
        'total_users': len(users),
        'users': [{'id': user.id, 'username': user.username} for user in users]
    }), 200

@bp.route('/semantic_info/<int:user_id>', methods=['GET'])
def get_user_semantic_info(user_id):
    """获取用户的语义信息统计
    
    返回用户设置的语义密码数量和伴生语义数量
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    # 获取用户的语义密码数量
    password_count = SemanticPassword.query.filter_by(user_id=user_id).count()
    
    # 获取用户的伴生语义数量
    companion_count = 0
    for password in SemanticPassword.query.filter_by(user_id=user_id).all():
        companion_count += CompanionSemantic.query.filter_by(semantic_password_id=password.id).count()
    
    # 统计状态
    has_completed_setup = password_count >= 3  # 通常需要设置3个语义密码
    
    return jsonify({
        'user_id': user_id,
        'username': user.username,
        'semantic_password_count': password_count,
        'companion_semantic_count': companion_count,
        'setup_completed': has_completed_setup
    }), 200

@bp.route('/status/<int:user_id>', methods=['GET'])
def get_user_status(user_id):
    """获取用户当前认证状态
    
    返回用户是否已完成语义密码设置、可用于验证的状态信息
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    # 检查语义密码状态
    semantics = SemanticPassword.query.filter_by(user_id=user_id).all()
    has_semantics = len(semantics) > 0
    
    # 检查伴生语义是否已生成
    companions_ready = False
    if has_semantics:
        # 检查第一个语义密码是否有伴生语义
        first_password = semantics[0]
        companions_ready = CompanionSemantic.query.filter_by(semantic_password_id=first_password.id).count() > 0
    
    return jsonify({
        'user_id': user_id,
        'username': user.username,
        'authentication_ready': has_semantics and companions_ready,
        'semantics_set': has_semantics,
        'companions_generated': companions_ready,
        'registration_completed': has_semantics
    }), 200

@bp.route('/reset_semantics/<int:user_id>', methods=['POST'])
def reset_user_semantics(user_id):
    """重置用户语义密码
    
    删除现有语义密码，允许用户重新选择
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    try:
        # 找到用户所有的语义密码
        semantic_passwords = SemanticPassword.query.filter_by(user_id=user_id).all()
        
        # 删除所有伴生语义和语义密码
        for password in semantic_passwords:
            # 删除伴生语义
            CompanionSemantic.query.filter_by(semantic_password_id=password.id).delete()
            # 删除语义密码
            db.session.delete(password)
        
        db.session.commit()
        
        return jsonify({
            'message': '语义密码已重置',
            'user_id': user_id,
            'next_step': '使用/auth/register重新提取语义，然后使用/auth/select_semantics选择语义密码'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"重置语义密码错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:user_id>/semantics', methods=['GET'])
def get_user_semantics(user_id):
    # 添加开发环境检查
    if not current_app.config.get('DEBUG', False):
        return jsonify({'error': '此接口仅在测试环境可用'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    # 获取用户语义密码
    semantic_passwords = SemanticPassword.query.filter_by(user_id=user_id).order_by(SemanticPassword.position).all()
    
    result = []
    for password in semantic_passwords:
        semantic = SemanticLibrary.query.get(password.semantic_id)
        if semantic:
            # 获取伴生语义
            companion_semantics = []
            for companion in CompanionSemantic.query.filter_by(semantic_password_id=password.id).order_by(CompanionSemantic.position).all():
                comp_semantic = SemanticLibrary.query.get(companion.semantic_id)
                if comp_semantic:
                    companion_semantics.append({
                        'position': companion.position,
                        'text': comp_semantic.semantic_text
                    })
            
            result.append({
                'position': password.position,
                'semantic_text': semantic.semantic_text,
                'companion_count': len(companion_semantics),
                'companions': companion_semantics
            })
    
    return jsonify({
        'user_id': user_id,
        'username': user.username,
        'semantic_count': len(result),
        'semantics': result
    }), 200

@bp.route('/<int:user_id>/companions/<int:semantic_position>', methods=['GET'])
def get_semantic_companions(user_id, semantic_position):
    """获取特定位置语义密码的伴生语义
    
    用于登录时展示语义密码的伴生语义
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    # 获取特定位置的语义密码
    semantic_password = SemanticPassword.query.filter_by(
        user_id=user_id, 
        position=semantic_position
    ).first()
    
    if not semantic_password:
        return jsonify({'error': f'用户在位置{semantic_position}没有语义密码'}), 404
    
    # 获取语义文本
    semantic = SemanticLibrary.query.get(semantic_password.semantic_id)
    
    # 获取伴生语义
    companions = []
    for companion in CompanionSemantic.query.filter_by(semantic_password_id=semantic_password.id).all():
        comp_semantic = SemanticLibrary.query.get(companion.semantic_id)
        if comp_semantic:
            companions.append({
                'position': companion.position,
                'text': comp_semantic.semantic_text
            })
    
    # 将正确的语义添加到列表中（前端需要打乱顺序）
    all_semantics = companions.copy()
    all_semantics.append({
        'position': -1,  # 特殊标记，表示这是正确的语义
        'text': semantic.semantic_text
    })
    
    # 随机排序
    random.shuffle(all_semantics)
    
    return jsonify({
        'user_id': user_id,
        'semantic_position': semantic_position,
        'total_options': len(all_semantics),
        'semantics': all_semantics
    }), 200

@bp.route('/info', methods=['GET'])
def get_user_info():
    """获取当前登录用户的信息
    
    用于前端显示用户信息
    """
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    # 返回用户信息
    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'registered_on': user.registered_on.isoformat()
    }), 200
