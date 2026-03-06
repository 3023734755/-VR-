from datetime import datetime, timedelta
import uuid
import hashlib
import hmac
from app import db

class AuthChallenge(db.Model):
    """认证挑战模型，用于存储用户登录时的挑战信息"""
    __tablename__ = 'auth_challenges'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    challenge_id = db.Column(db.String(36), unique=True, nullable=False)  # UUID
    nonce = db.Column(db.String(36), nullable=False)  # 一次性随机数
    server_signature = db.Column(db.String(128), nullable=False)  # 服务器签名
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    used = db.Column(db.Boolean, default=False)  # 是否已使用
    expires_at = db.Column(db.DateTime, nullable=False)  # 过期时间
    
    def __repr__(self):
        return f'<AuthChallenge {self.challenge_id}>'
    
    @classmethod
    def create_challenge(cls, user_id, server_key):
        """
        创建新的认证挑战
        """
        # 生成唯一的挑战ID和随机数
        challenge_id = str(uuid.uuid4())
        nonce = str(uuid.uuid4())
        
        # 计算服务器签名 (HMAC-SHA256)
        signature_message = f"{challenge_id}:{nonce}:{user_id}"
        server_signature = hmac.new(
            server_key.encode('utf-8'),
            signature_message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # 设置过期时间 (15分钟)
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        # 创建挑战记录
        challenge = cls(
            user_id=user_id,
            challenge_id=challenge_id,
            nonce=nonce,
            server_signature=server_signature,
            expires_at=expires_at
        )
        
        # 保存到数据库
        db.session.add(challenge)
        db.session.commit()
        
        return challenge
    
    def to_dict(self):
        """
        将挑战对象转换为字典，用于API响应
        """
        from app.models.models import User
        user = User.query.get(self.user_id)
        
        return {
            'username': user.username,
            'challenge_id': self.challenge_id,
            'nonce': self.nonce,
            'timestamp': int(self.timestamp.timestamp()),
            'server_signature': self.server_signature
        }
    
    def is_valid(self):
        """
        检查挑战是否有效
        """
        now = datetime.utcnow()
        return not self.used and now < self.expires_at
    
    def mark_used(self):
        """
        将挑战标记为已使用
        """
        self.used = True
        db.session.commit() 