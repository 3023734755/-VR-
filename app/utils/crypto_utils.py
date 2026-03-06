import hashlib
import hmac
import base64
import json
import os
import time  # 从crypto.py导入
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from flask import current_app
import uuid
import logging

# 注意: 此文件合并了原crypto.py和crypto_utils.py的功能
logger = logging.getLogger(__name__)

# ==== 从crypto.py导入的基本功能 ====

def generate_random_bytes(length=32):
    """生成指定长度的随机字节"""
    return os.urandom(length)

def generate_nonce():
    """生成一个唯一的随机nonce"""
    # 结合时间戳和随机字节，确保唯一性
    timestamp = str(time.time()).encode()
    random_bytes = generate_random_bytes(16)
    combined = timestamp + random_bytes
    # 使用Base64编码，使其适合在JSON中传输
    return base64.urlsafe_b64encode(combined).decode('utf-8')

def generate_signature(message, secret_key):
    """使用HMAC-SHA256生成消息签名
    
    Args:
        message: 要签名的消息
        secret_key: 服务器私钥
        
    Returns:
        base64编码的签名
    """
    if isinstance(message, str):
        message = message.encode('utf-8')
    if isinstance(secret_key, str):
        secret_key = secret_key.encode('utf-8')
        
    signature = hmac.new(secret_key, message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).decode('utf-8')

def verify_signature(message, signature, secret_key):
    """验证HMAC消息签名
    
    Args:
        message: 原始消息
        signature: 收到的签名
        secret_key: 用于验证的密钥
        
    Returns:
        验证结果(True/False)
    """
    expected_sig = generate_signature(message, secret_key)
    # 使用constant_time_compare防止时序攻击
    return hmac.compare_digest(signature, expected_sig)

def get_current_timestamp():
    """获取当前时间戳的ISO格式"""
    return datetime.utcnow().isoformat()

# ==== 原crypto_utils.py的高级功能 ====

class CryptoManager:
    """加密管理器"""
    
    def __init__(self):
        self.server_private_key = None
        self.server_public_key = None
        self._load_or_generate_server_keys()
    
    def _load_or_generate_server_keys(self):
        """加载或生成服务器密钥对"""
        try:
            # 尝试从文件加载
            private_key_path = 'server_private_key.pem'
            public_key_path = 'server_public_key.pem'
            
            if os.path.exists(private_key_path) and os.path.exists(public_key_path):
                with open(private_key_path, 'rb') as f:
                    self.server_private_key = serialization.load_pem_private_key(
                        f.read(), password=None, backend=default_backend()
                    )
                with open(public_key_path, 'rb') as f:
                    self.server_public_key = serialization.load_pem_public_key(
                        f.read(), backend=default_backend()
                    )
                logger.info("服务器密钥对加载成功")
            else:
                # 生成新的密钥对
                self._generate_server_keys()
                logger.info("生成新的服务器密钥对")
        except Exception as e:
            logger.error(f"密钥加载失败: {e}")
            self._generate_server_keys()
    
    def _generate_server_keys(self):
        """生成服务器密钥对"""
        self.server_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.server_public_key = self.server_private_key.public_key()
        
        # 保存密钥到文件
        try:
            with open('server_private_key.pem', 'wb') as f:
                f.write(self.server_private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            with open('server_public_key.pem', 'wb') as f:
                f.write(self.server_public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
        except Exception as e:
            logger.warning(f"密钥保存失败: {e}")
    
    def generate_user_keys(self):
        """为用户生成密钥对"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        # 序列化密钥
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return private_pem, public_pem
    
    def sign_data(self, data, private_key=None):
        """使用私钥签名数据"""
        if private_key is None:
            private_key = self.server_private_key
        
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        signature = private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode('utf-8')
    
    def verify_signature(self, data, signature, public_key):
        """验证RSA签名 (不同于HMAC签名验证)"""
        try:
            if isinstance(data, dict):
                data = json.dumps(data, sort_keys=True)
            
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            signature_bytes = base64.b64decode(signature)
            
            if isinstance(public_key, str):
                public_key = serialization.load_pem_public_key(
                    public_key.encode('utf-8'),
                    backend=default_backend()
                )
            
            public_key.verify(
                signature_bytes,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            logger.warning(f"签名验证失败: {e}")
            return False
    
    def generate_challenge_id(self):
        """生成挑战ID"""
        return str(uuid.uuid4())
    
    def create_server_signature(self, challenge_data):
        """创建服务器签名"""
        return self.sign_data(challenge_data)
    
    def get_server_public_key_pem(self):
        """获取服务器公钥PEM格式"""
        return self.server_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

# 全局加密管理器实例
crypto_manager = None

def get_crypto_manager():
    """获取加密管理器实例"""
    global crypto_manager
    if crypto_manager is None:
        crypto_manager = CryptoManager()
    return crypto_manager


# 添加密码哈希函数
from werkzeug.security import generate_password_hash, check_password_hash

def get_password_hash(password):
    """生成密码哈希"""
    return generate_password_hash(password)

def verify_password_hash(password_hash, password):
    """验证密码哈希"""
    return check_password_hash(password_hash, password)