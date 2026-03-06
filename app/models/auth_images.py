from datetime import datetime
from app import db
from sqlalchemy.exc import SQLAlchemyError
import os
from flask import current_app

class AuthImage(db.Model):
    """认证图片模型，存储用户认证图片的相关信息"""
    __tablename__ = 'auth_images'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # 对应语义密码的位置
    image_path = db.Column(db.String(255), nullable=False)  # 图片相对路径
    is_password_image = db.Column(db.Boolean, default=False)  # 是否包含密码语义
    semantic1_id = db.Column(db.Integer, db.ForeignKey('semantic_library.id'), nullable=True)  # 第一个语义ID
    semantic2_id = db.Column(db.Integer, db.ForeignKey('semantic_library.id'), nullable=True)  # 第二个语义ID（可选）
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 定义关系
    semantic1 = db.relationship('SemanticLibrary', foreign_keys=[semantic1_id], lazy='joined')
    semantic2 = db.relationship('SemanticLibrary', foreign_keys=[semantic2_id], lazy='joined')
    
    def __repr__(self):
        return f'<AuthImage User:{self.user_id} Pos:{self.position} Password:{self.is_password_image}>'
    
    def to_dict(self):
        """
        将图片对象转换为字典，用于API响应
        """
        return {
            'id': self.id,
            'position': self.position,
            'image_path': self.image_path,
            'image_url': self.get_image_url(),
            'is_password_image': self.is_password_image,
            'created_on': self.created_on.isoformat()
        }
    
    def get_image_url(self):
        """
        获取图片URL路径
        """
        image_path = self.image_path
        
        # 检查路径是否是绝对路径
        if os.path.isabs(image_path):
            # 转换为相对URL路径
            base_dir = current_app.config.get('BASE_DIR')
            if image_path.startswith(base_dir):
                # 从绝对路径中提取相对路径部分
                rel_path = os.path.relpath(image_path, base_dir)
                url_path = rel_path.replace('\\', '/')
            else:
                # 如果不是以BASE_DIR开头，尝试从用户ID获取用户名
                from app.models.models import User
                user = User.query.get(self.user_id)
                if user:
                    url_path = f"user_images/{user.username}/pos{self.position+1}/{os.path.basename(image_path)}"
                else:
                    url_path = f"user_images/user_{self.user_id}/pos{self.position+1}/{os.path.basename(image_path)}"
        else:
            # 已经是相对路径
            url_path = image_path
            
        return f'/{url_path}'
    
    def get_semantic_info(self):
        """
        获取图片中的语义信息
        """
        semantics = []
        
        if self.semantic1:
            semantics.append({
                'id': self.semantic1.id,
                'text': self.semantic1.semantic_text,
                'category': self.semantic1.category
            })
            
        if self.semantic2:
            semantics.append({
                'id': self.semantic2.id,
                'text': self.semantic2.semantic_text,
                'category': self.semantic2.category
            })
            
        return {
            'semantics': semantics,
            'count': len(semantics)
        }
    
    @classmethod
    def get_auth_images_for_user(cls, user_id, position=None):
        """
        获取用户的认证图片
        """
        query = cls.query.filter_by(user_id=user_id)
        if position is not None:
            query = query.filter_by(position=position)
        
        return query.all()
    
    @classmethod
    def get_random_images_for_position(cls, user_id, position, count=9):
        """
        获取指定位置的认证图片，确保返回准确的9张图片（1张包含密码，8张干扰）
        """
        import random
        
        # 获取该位置的所有图片
        password_images = cls.query.filter_by(user_id=user_id, position=position, is_password_image=True).all()
        non_password_images = cls.query.filter_by(user_id=user_id, position=position, is_password_image=False).all()
        
        # 确保有密码图片
        if not password_images:
            current_app.logger.warning(f"用户 {user_id} 在位置 {position} 没有密码图片")
            # 如果没有密码图片，从其他位置获取图片或创建默认图片
            # 尝试从其他位置获取密码图片
            all_password_images = cls.query.filter_by(user_id=user_id, is_password_image=True).all()
            if all_password_images:
                selected_password_image = random.choice(all_password_images)
                result = [selected_password_image]
            else:
                # 如果根本没有密码图片，返回所有可用的非密码图片
                current_app.logger.error(f"用户 {user_id} 没有任何密码图片")
                return non_password_images[:count] if non_password_images else []
        else:
            # 选择1张密码图片
            selected_password_image = random.choice(password_images)
            result = [selected_password_image]
        
        # 需要8张干扰图片
        remaining_count = count - 1
        if remaining_count > 0:
            # 如果非密码图片不足8张
            if len(non_password_images) < remaining_count:
                current_app.logger.warning(f"用户 {user_id} 在位置 {position} 干扰图片不足，只有 {len(non_password_images)} 张")
                
                # 使用所有可用的非密码图片
                result.extend(non_password_images)
                
                # 如果还不够，使用其他密码图片（除了已选择的那一张）填充
                additional_password_images = [img for img in password_images if img.id != selected_password_image.id]
                
                # 如果还需要更多图片
                if len(result) < count:
                    # 如果有其他密码图片
                    if additional_password_images:
                        # 计算还需要多少图片
                        still_needed = min(count - len(result), len(additional_password_images))
                        # 取可用密码图片的子集
                        to_add = random.sample(additional_password_images, still_needed)
                        result.extend(to_add)
                    
                    # 如果仍然不够，从其他位置获取干扰图片
                    if len(result) < count:
                        other_images = cls.query.filter(
                            cls.user_id == user_id,
                            cls.position != position,
                            cls.is_password_image == False
                        ).all()
                        
                        if other_images:
                            still_needed = count - len(result)
                            to_add = random.sample(other_images, min(still_needed, len(other_images)))
                            result.extend(to_add)
            else:
                # 有足够的非密码图片，随机选择8张
                selected_non_password = random.sample(non_password_images, remaining_count)
                result.extend(selected_non_password)
        
        # 确保结果数量正确
        while len(result) < count:
            # 如果所有尝试后仍然不足9张，创建重复
            current_app.logger.warning(f"用户 {user_id} 图片不足9张，使用已有图片重复填充")
            if len(result) > 0:
                # 从已有结果中随机选择一张复制
                duplicate = random.choice(result)
                result.append(duplicate)
            else:
                break  # 避免死循环
        
        # 随机打乱顺序
        random.shuffle(result)
        
        current_app.logger.info(f"返回认证图片: 总共 {len(result)} 张，其中 {sum(1 for img in result if img.is_password_image)} 张包含密码")
        
        return result[:count]  # 确保只返回指定数量的图片
    
    @classmethod
    def create_from_generated_image(cls, user_id, position, image_path, semantic1_id=None, semantic2_id=None, is_password_image=False):
        """
        从生成的图片创建认证图片记录
        """
        try:
            auth_image = cls(
                user_id=user_id,
                position=position,
                image_path=image_path,
                semantic1_id=semantic1_id,
                semantic2_id=semantic2_id,
                is_password_image=is_password_image
            )
            
            db.session.add(auth_image)
            # 移除db.session.commit()，让外层函数统一管理事务
            
            return auth_image
            
        except SQLAlchemyError as e:
            current_app.logger.error(f"创建认证图片记录失败: {str(e)}")
            db.session.rollback()
            return None 