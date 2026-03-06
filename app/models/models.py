from datetime import datetime
from app import db
import random
import os
from app.models.auth_challenge import AuthChallenge  # 从专用模块导入AuthChallenge
from app.models.auth_images import AuthImage  # 从专用模块导入AuthImage

# 用户表
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    registered_on = db.Column(db.DateTime, default=datetime.utcnow)
    semantic_passwords = db.relationship('SemanticPassword', backref='user', lazy='dynamic')
    auth_challenges = db.relationship('AuthChallenge', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    @classmethod
    def get_by_username(cls, username):
        """通过用户名获取用户，区分大小写"""
        return cls.query.filter(db.func.lower(cls.username) == db.func.lower(username)).first()
    
    def get_semantic_passwords_with_details(self):
        """获取用户所有语义密码及详细信息"""
        result = []
        passwords = SemanticPassword.query.filter_by(user_id=self.id).all()
        
        for password in passwords:
            semantic = SemanticLibrary.query.get(password.semantic_id)
            companions = CompanionSemantic.query.filter_by(semantic_password_id=password.id).all()
            
            result.append({
                'position': password.position,
                'semantic': {
                    'id': semantic.id,
                    'text': semantic.semantic_text,
                    'category': semantic.category
                },
                'companions_count': len(companions)
            })
            
        return result
    
    def reset_failed_attempts(self):
        pass
        
    def record_login_attempt(self, success=True):
        pass

# 语义库表 - 存储所有系统生成的语义
class SemanticLibrary(db.Model):
    __tablename__ = 'semantic_library'
    id = db.Column(db.Integer, primary_key=True)
    semantic_text = db.Column(db.String(255), nullable=False, unique=True, index=True)
    category = db.Column(db.String(20), nullable=True, index=True)  # 'subject', 'environment', 'behavior'
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Semantic {self.semantic_text[:20]}...>'

# 语义密码表 - 存储用户选择的语义密码
class SemanticPassword(db.Model):
    __tablename__ = 'semantic_passwords'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    semantic_id = db.Column(db.Integer, db.ForeignKey('semantic_library.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # 密码中的位置顺序
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    companion_semantics = db.relationship('CompanionSemantic', backref='password', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'position', name='unique_user_position'),
    )
    
    def __repr__(self):
        return f'<SemanticPassword User:{self.user_id} Pos:{self.position}>'

# 伴生语义表 - 存储每个语义密码对应的伴生语义
class CompanionSemantic(db.Model):
    __tablename__ = 'companion_semantics'
    id = db.Column(db.Integer, primary_key=True)
    semantic_password_id = db.Column(db.Integer, db.ForeignKey('semantic_passwords.id'), nullable=False)
    semantic_id = db.Column(db.Integer, db.ForeignKey('semantic_library.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)  # 伴生语义的位置顺序
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('semantic_password_id', 'position', name='unique_password_position'),
    )
    
    def __repr__(self):
        return f'<CompanionSemantic Password:{self.semantic_password_id} Pos:{self.position}>'

# 注：AuthImage类已移至app/models/auth_images.py
# 注：AuthChallenge类已移至app/models/auth_challenge.py
