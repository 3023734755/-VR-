from flask import Flask, jsonify, send_from_directory, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from config import Config
import os
import time
from flask import current_app

# 初始化扩展
db = SQLAlchemy()
migrate = Migrate()

# 添加全局变量，用于存储模型和分词器
qwen_model = None
qwen_tokenizer = None

# 创建一个函数，用于加载AI模型
def load_ai_models(app):
    """加载AI模型的函数，将在应用上下文中被调用"""
    if app.config.get('USE_AI_MODEL', False):
        try:
            global qwen_model, qwen_tokenizer
            
            import torch
            import transformers
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            app.logger.info(f"当前transformers库版本: {transformers.__version__}")
            
            # 设置模型路径
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'models', 'Qwen1.5-1.8B-Chat')
            
            # 检查模型路径是否存在
            if not os.path.exists(model_path):
                app.logger.warning(f"模型路径不存在: {model_path}，将使用模板生成故事")
                return False
            
            app.logger.info(f"加载故事生成模型: {model_path}")
            
            try:
                # 使用story_generator中的方法加载模型
                from app.semantic.story_generator import get_story_generator
                story_gen = get_story_generator()
                if not story_gen.load_model():
                    app.logger.error("故事生成模型加载失败")
                    return False
                app.logger.info("故事生成模型加载成功")
                return True
            except Exception as e:
                app.logger.error(f"加载故事生成模型失败: {str(e)}")
                import traceback
                app.logger.error(traceback.format_exc())
                return False
            
        except Exception as e:
            app.logger.error(f"加载模型失败: {str(e)}")
            import traceback
            app.logger.error(traceback.format_exc())
            return False
    else:
        app.logger.info("AI模型功能已禁用")
        return False

# 创建一个函数，用于加载语义标签提取模型
def load_semantic_model(app):
    """加载语义标签提取模型的函数，将在应用上下文中被调用"""
    try:
        app.logger.info("开始加载语义标签提取模型...")
        from app.semantic.semantic_labeler import load_semantic_model
        if load_semantic_model():
            app.logger.info("语义标签提取模型加载成功")
            return True
        else:
            app.logger.warning("语义标签提取模型加载失败，将使用备用方法提取语义")
            return False
    except Exception as e:
        app.logger.error(f"加载语义标签提取模型失败: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return False

# 创建一个函数，用于在应用启动时检测并预热模型
def preload_and_warmup_models(app):
    """在应用启动时检测并预热模型"""
    app.logger.info("开始检测并预热模型...")
    start_time = time.time()
    
    # 检测并加载故事生成模型
    story_model_loaded = load_ai_models(app)
    if story_model_loaded:
        app.logger.info("故事生成模型预热完成")
    else:
        app.logger.warning("故事生成模型加载失败，将使用模板方法")
    
    # 检测并加载语义标签提取模型
    semantic_model_loaded = load_semantic_model(app)
    if semantic_model_loaded:
        app.logger.info("语义标签提取模型预热完成")
    else:
        app.logger.warning("语义标签提取模型加载失败，将使用备用方法")
    
    # 检查模型加载状态
    if story_model_loaded and semantic_model_loaded:
        app.logger.info("所有模型加载成功")
        status = "成功"
    elif story_model_loaded:
        app.logger.warning("仅故事生成模型加载成功")
        status = "部分成功"
    elif semantic_model_loaded:
        app.logger.warning("仅语义标签提取模型加载成功")
        status = "部分成功"
    else:
        app.logger.error("所有模型加载失败")
        status = "失败"
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    app.logger.info(f"模型检测与预热完成，状态: {status}，耗时: {elapsed_time:.2f}秒")
    
    # 返回模型加载状态
    return {
        "status": status,
        "story_model_loaded": story_model_loaded,
        "semantic_model_loaded": semantic_model_loaded,
        "elapsed_time": elapsed_time
    }

def create_app(config_class=Config):
    # 指定模板文件夹的路径为项目根目录下的templates
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    app = Flask(__name__, 
                template_folder=template_path,  # 使用绝对路径
                static_folder=static_path)
    app.config.from_object(config_class)
    
    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)  # 启用跨域支持，便于Unity前端与Flask后端通信
    
    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['IMAGE_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEXT_UPLOAD_FOLDER'], exist_ok=True)
    
    # 确保用户图像目录存在
    user_images_dir = os.path.join(app.config['BASE_DIR'], 'user_images')
    os.makedirs(user_images_dir, exist_ok=True)
    
    # 配置文件类型检测（兼容无python-magic的环境）
    app.config['USE_MAGIC_LIB'] = False
    try:
        import magic
        app.config['USE_MAGIC_LIB'] = True
    except ImportError:
        app.logger.warning("python-magic未安装，使用文件扩展名验证文件类型")
    
    # 配置OCR（如果使用）
    try:
        import pytesseract
        if os.path.exists(app.config['TESSERACT_CMD']):
            pytesseract.pytesseract.tesseract_cmd = app.config['TESSERACT_CMD']
    except ImportError:
        app.logger.warning("pytesseract not installed, OCR functionality will be limited")
    
    
    # 注册蓝图
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.user import bp as user_bp
    app.register_blueprint(user_bp, url_prefix='/user')
    
    # 注册语义标签路由
    from app.routes.semantic_routes import register_semantic_routes
    register_semantic_routes(app)
    
    # 添加模型状态检查路由
    @app.route('/api/model_status')
    def model_status():
        """返回模型加载状态"""
        from app.semantic.story_generator import get_story_generator
        from app.semantic.semantic_labeler import bert_model
        
        story_gen = get_story_generator()
        story_model_loaded = story_gen.loaded if hasattr(story_gen, 'loaded') else False
        semantic_model_loaded = bert_model is not None
        
        return jsonify({
            'story_model_loaded': story_model_loaded,
            'semantic_model_loaded': semantic_model_loaded
        })
    
    # 添加用户图像文件路由
    @app.route('/user_images/<path:filename>')
    def user_images(filename):
        """提供用户图像文件"""
        app.logger.info(f"请求用户图像: {filename}")
        user_images_path = os.path.join(app.config['BASE_DIR'], 'user_images')
        return send_from_directory(user_images_path, filename)
    
    # 添加根路径处理
    @app.route('/')
    def index():
        # 返回主页
        try:
            return render_template('index.html')
        except Exception as e:
            app.logger.error(f"渲染index.html时出错: {str(e)}")
            return f"渲染页面时出错: {str(e)}", 500
    
    # 添加登录路由
    @app.route('/login')
    def login():
        try:
            return render_template('login.html')
        except Exception as e:
            app.logger.error(f"渲染login.html时出错: {str(e)}")
            return f"渲染登录页面时出错: {str(e)}", 500
    
    # 注册错误处理
    from app.utils import errors
    errors.register_error_handlers(app)
    
    # 导入初始化数据库函数
    with app.app_context():
        from app.models.init_db import init_semantic_library
        # 创建所有表（如果不存在）
        db.create_all()
        # 初始化语义库
        init_semantic_library()
    
    # 在应用启动时检测并预热模型
    with app.app_context():
        model_status = preload_and_warmup_models(app)
        app.config['MODEL_STATUS'] = model_status
    
    return app

from app import models  # 确保模型被导入
