import os

class Config:
    # 服务器配置
    PORT = int(os.environ.get('PORT', 5000))  # 应用端口配置，改回5000
    
    # 秘钥配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production')
    # 服务器签名密钥 - 用于登录挑战签名
    SERVER_SIGNATURE_KEY = os.environ.get('SERVER_SIGNATURE_KEY') or 'secure-server-signature-key'
    
    # 会话配置
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 86400  # 会话有效期为1天（秒）
    
    # 数据库配置
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'zhan114923')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DB_NAME', 'semantic_auth')
    
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 上传文件配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    IMAGE_UPLOAD_FOLDER = os.environ.get('IMAGE_UPLOAD_FOLDER', os.path.join(UPLOAD_FOLDER, 'images'))
    TEXT_UPLOAD_FOLDER = os.environ.get('TEXT_UPLOAD_FOLDER', os.path.join(UPLOAD_FOLDER, 'texts'))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 限制上传大小为16MB
    
    # 语义提取配置
    SEMANTIC_COUNT = 3  # 用户选择的语义数量
    COMPANION_SEMANTIC_COUNT = 17  # 每个语义密码对应的伴生语义数量
    SEMANTIC_EXTRACT_COUNT = 20  # 提取的语义数量
    
    # OCR配置
    TESSERACT_CMD = os.environ.get('TESSERACT_CMD') or r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    # 支持的文件类型
    ALLOWED_TEXT_EXTENSIONS = {'txt', 'doc', 'docx', 'pdf', 'md'}
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    
    # 图片生成配置
    USER_IMAGES_FOLDER = os.environ.get('USER_IMAGES_FOLDER', os.path.join(BASE_DIR, 'user_images'))
    IMAGES_PER_POSITION = 9  # 每个语义密码位置生成的图片数量
    HUNYUAN_MODEL_PATH = os.environ.get('HUNYUAN_MODEL_PATH') or os.path.join(BASE_DIR, 'app', 'models', 'hunyuan-dit')  # Hunyuan模型路径
    USE_XFORMERS = os.environ.get('USE_XFORMERS', 'True').lower() in ('true', '1', 't')  # 是否使用xformers优化
    
    # SSL证书配置（已禁用）
    # SSL_CERT = os.environ.get('SSL_CERT', os.path.join(BASE_DIR, 'ssl', 'cert.pem'))
    # SSL_KEY = os.environ.get('SSL_KEY', os.path.join(BASE_DIR, 'ssl', 'key.pem'))
    SSL_ENABLED = False  # 强制禁用HTTPS

    # 故事生成配置
    STORY_MODEL_PATH = os.environ.get('STORY_MODEL_PATH') or os.path.join(BASE_DIR, 'app', 'models', 'Qwen1.5-1.8B-Chat')
    USE_GPU = os.environ.get('USE_GPU', 'True').lower() in ('true', '1', 't')  # 是否使用GPU
    STORIES_COUNT = 3  # 生成的故事数量

    # 语义标签提取配置
    SEMANTIC_MODEL_PATH = os.environ.get('SEMANTIC_MODEL_PATH') or os.path.join(BASE_DIR, 'app', 'models', 'chinese-bert-wwm-ext')
    SEMANTIC_LABELS_PER_CATEGORY = 3  # 每个类别提取的标签数量
    
    # 注册流程配置
    SEMANTIC_CANDIDATES_COUNT = 30  # 每个类别提供的候选语义数量

    # 在线API配置
    DOUBAO_API_KEY = os.environ.get('DOUBAO_API_KEY') or "a441641d-5cf7-4e44-931a-9a159c88290b"
    DOUBAO_API_URL = os.environ.get('DOUBAO_API_URL') or "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    DOUBAO_MODEL_VERSION = os.environ.get('DOUBAO_MODEL_VERSION') or "doubao-seedream-3-0-t2i-250415"
    USE_ONLINE_GENERATION = os.environ.get('USE_ONLINE_GENERATION', 'True').lower() in ('true', '1', 't')  # 是否使用在线生成
    DISABLE_WATERMARK = os.environ.get('DISABLE_WATERMARK', 'True').lower() in ('true', '1', 't')  # 是否禁用水印

    # AI模型设置
    USE_AI_MODEL = True

    # 模型配置
    MODEL_PATH = os.environ.get('MODEL_PATH', 'models')
