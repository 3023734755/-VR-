import hashlib
import hmac
import json
import time
import uuid

from flask import current_app

from app.utils.redis_client import get_redis

# 挑战票据有效期（秒）：15 分钟
CHALLENGE_TTL = 900
# Redis 键前缀
CHALLENGE_KEY_PREFIX = 'challenge:'


class AuthChallenge:
    """认证挑战票据（存储于 Redis）

    相比原 MySQL 版本的设计改进：
    1. TTL 即有效期 —— SETEX 写入时设置过期时间，过期由 Redis 自动删除，
       不再依赖应用层 expires_at 字段；
    2. "已使用" = 删除键 —— DEL 是原子命令，返回删除的键数；
       第一个消费成功的请求返回 1，并发重放的请求返回 0 直接拒绝，
       消除了原版本 mark_used() 读-改-写（read-modify-write）的并发竞态；
    3. 票据是短生命周期热数据，放 Redis 减少 MySQL 写压力。
    """

    def __init__(self, challenge_id, user_id, nonce, server_signature, timestamp):
        self.challenge_id = challenge_id
        self.user_id = user_id
        self.nonce = nonce
        self.server_signature = server_signature
        self.timestamp = timestamp

    @staticmethod
    def _key(challenge_id):
        return f'{CHALLENGE_KEY_PREFIX}{challenge_id}'

    @property
    def key(self):
        return self._key(self.challenge_id)

    @classmethod
    def create_challenge(cls, user_id, server_key):
        """创建挑战票据并写入 Redis（带 15 分钟 TTL）"""
        challenge_id = str(uuid.uuid4())
        nonce = str(uuid.uuid4())

        # HMAC-SHA256 服务器签名：challenge_id:nonce:user_id
        signature_message = f"{challenge_id}:{nonce}:{user_id}"
        server_signature = hmac.new(
            server_key.encode('utf-8'),
            signature_message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        timestamp = int(time.time())

        payload = {
            'challenge_id': challenge_id,
            'user_id': user_id,
            'nonce': nonce,
            'server_signature': server_signature,
            'timestamp': timestamp,
        }
        # SETEX：写入即带过期时间，原子完成
        get_redis().setex(cls._key(challenge_id), CHALLENGE_TTL, json.dumps(payload))

        return cls(challenge_id, user_id, nonce, server_signature, timestamp)

    @classmethod
    def get(cls, challenge_id):
        """从 Redis 读取票据，不存在或已过期返回 None"""
        raw = get_redis().get(cls._key(challenge_id))
        if raw is None:
            return None
        data = json.loads(raw.decode('utf-8'))
        return cls(
            challenge_id=data['challenge_id'],
            user_id=data['user_id'],
            nonce=data['nonce'],
            server_signature=data['server_signature'],
            timestamp=data['timestamp'],
        )

    def is_valid(self):
        """票据有效 = 键仍存在（TTL 负责过期，删除负责"已使用"）"""
        return get_redis().exists(self.key) == 1

    def mark_used(self):
        """原子消费票据：删除成功返回 True，已被并发消费返回 False

        只有第一个执行 DEL 的请求能拿到返回值 1，其余并发请求拿到 0，
        因此调用方拿到 False 时必须中止流程 —— 这是防重放的关键。
        """
        return get_redis().delete(self.key) == 1

    def to_dict(self):
        """转换为 API 响应格式（与原 MySQL 版本保持一致）"""
        from app.models.models import User
        user = User.query.get(self.user_id)

        return {
            'username': user.username if user else None,
            'challenge_id': self.challenge_id,
            'nonce': self.nonce,
            'timestamp': self.timestamp,
            'server_signature': self.server_signature
        }

    def __repr__(self):
        return f'<AuthChallenge {self.challenge_id}>'
