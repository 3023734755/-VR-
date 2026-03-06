"""
认证图片处理工具
"""
import os
import logging
from app import db
from app.models.auth_images import AuthImage
from flask import current_app

logger = logging.getLogger(__name__)

def record_auth_images(user_id, semantic_passwords_data, user_dir):
    """
    记录用户认证图片信息到数据库
    
    Args:
        user_id: 用户ID
        semantic_passwords_data: 语义密码数据，包含位置、密码和伴生语义
        user_dir: 用户图片文件夹路径
        
    Returns:
        int: 成功记录的图片数量
    """
    try:
        total_recorded = 0
        
        # 处理每个位置的图片
        for password_data in semantic_passwords_data:
            position = password_data['position']
            password_id = password_data['password_id']
            companions_ids = password_data.get('companions_ids', [])
            
            # 获取该位置图片目录
            pos_dir = os.path.join(user_dir, f"pos{position}")
            if not os.path.exists(pos_dir):
                logger.error(f"位置{position}的图片目录不存在: {pos_dir}")
                continue
                
            # 获取目录中的所有图片
            for filename in os.listdir(pos_dir):
                if not filename.endswith(('.png', '.jpg', '.jpeg')):
                    continue
                    
                image_path = os.path.join(pos_dir, filename)
                # 仅存储相对路径，方便后续迁移
                rel_path = os.path.relpath(
                    image_path, 
                    os.path.dirname(user_dir)
                )
                
                # 确定该图片是否包含密码语义
                # 注意: 在实际实现中，您需要知道哪些图片包含真实密码
                # 这里我们使用一个简单的规则：每个位置的第一张图片包含密码
                is_password_image = filename.startswith(('password_', 'semantic_'))
                
                # 为简化起见，我们假设每个图片包含密码语义和一个伴生语义
                # 在实际实现中，您需要知道每个图片包含哪些语义
                semantic1_id = password_id  # 主语义ID
                
                # 随机选择一个伴生语义ID，或者使用密码ID（对于纯密码图片）
                semantic2_id = password_id if is_password_image else \
                    (companions_ids[0] if companions_ids else None)
                
                # 创建图片记录
                auth_image = AuthImage(
                    user_id=user_id,
                    position=position,
                    image_path=rel_path,
                    is_password_image=is_password_image,
                    semantic1_id=semantic1_id,
                    semantic2_id=semantic2_id
                )
                
                db.session.add(auth_image)
                total_recorded += 1
        
        # 提交所有图片记录
        db.session.commit()
        logger.info(f"已成功记录{total_recorded}张认证图片")
        return total_recorded
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"记录认证图片信息失败: {str(e)}")
        return 0
