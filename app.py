import os
from flask import Flask, render_template, redirect, url_for, session, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from config import Config

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='templates',  # 使用绝对路径
                static_folder='static')
    app.config.from_object(config_class)
    
    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    
    # 启用CORS跨域支持
    CORS(app)
    
    # 创建必要的目录
    os.makedirs(app.config['IMAGE_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEXT_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['USER_IMAGES_FOLDER'], exist_ok=True)
    
    # SSL证书目录配置已移除
    # ssl_dir = os.path.dirname(app.config['SSL_CERT'])
    # if ssl_dir:
    #     os.makedirs(ssl_dir, exist_ok=True)
    
    # 注册蓝图
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.user import bp as user_bp
    app.register_blueprint(user_bp, url_prefix='/user')
    
    # 主页路由 - API响应
    @app.route('/api')
    def api_index():
        return {
            'name': 'Semantic Authentication API',
            'version': '1.0',
            'description': '基于语义的认证系统API',
            'endpoints': {
                'auth': '/auth/*',
                'user': '/user/*'
            }
        }
    
    # 主页路由 - Web前端
    @app.route('/')
    def index():
        try:
            return render_template('index.html')
        except Exception as e:
            app.logger.error(f"渲染index.html时出错: {str(e)}")
            return f"渲染页面时出错: {str(e)}", 500
    
    # 注册页面
    @app.route('/register')
    def register():
        try:
            return render_template('register.html')
        except Exception as e:
            app.logger.error(f"渲染register.html时出错: {str(e)}")
            return f"渲染注册页面时出错: {str(e)}", 500
    
    # 登录页面
    @app.route('/login')
    def auth_login():
        try:
            return render_template('login.html')
        except Exception as e:
            app.logger.error(f"渲染login.html时出错: {str(e)}")
            return f"渲染登录页面时出错: {str(e)}", 500
    
    # 仪表板页面
    @app.route('/dashboard')
    def dashboard():
        # 检查用户是否已登录
        if 'user_id' not in session:
            return redirect(url_for('auth_login'))
        return render_template('dashboard.html')
    
    # 退出登录
    @app.route('/logout')
    def logout():
        # 清除会话
        session.clear()
        return redirect(url_for('index'))
    
    # 注册错误处理程序
    from app.utils.errors import register_error_handlers
    register_error_handlers(app)
    
    return app

# 创建应用实例（供run.py使用）
app = create_app()
with app.app_context():
    try:
        from app.models.init_db import init_database
        init_database()
    except Exception as e:
        app.logger.error(f"数据库初始化失败: {str(e)}")

if __name__ == "__main__":
    # 如果直接运行此文件，则启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)
