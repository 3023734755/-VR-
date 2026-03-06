import os
import sys
import logging
import webbrowser
import time
import threading
import traceback

# 确保日志目录存在
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'semantic_auth_app.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("应用启动中...")

def is_port_in_use(port):
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def check_mysql_server():
    """检查MySQL服务器是否运行"""
    try:
        # 从配置文件获取数据库连接信息
        from config import Config
        db_url = Config.SQLALCHEMY_DATABASE_URI
        
        # 如果不是MySQL，直接返回True
        if 'mysql' not in db_url.lower():
            logger.info("非MySQL数据库，跳过MySQL服务检查")
            return True
            
        # 解析数据库URL
        import pymysql
        from urllib.parse import urlparse
        
        # 提取用户名和密码
        if '@' in db_url:
            auth_part = db_url.split('@')[0].split('://')[-1]
            if ':' in auth_part:
                user, password = auth_part.split(':')
            else:
                user, password = auth_part, None
        else:
            user, password = 'root', None
            
        # 简单解析，仅用于检查服务器
        parts = db_url.split('@')
        if len(parts) > 1:
            host_part = parts[1].split('/')[0]
        else:
            host_part = parts[0].split('/')[0]
            
        if ':' in host_part:
            host, port = host_part.split(':')
            port = int(port)
        else:
            host = host_part
            port = 3306
            
        # 尝试连接MySQL服务器
        logger.info(f"尝试连接MySQL服务器 {host}:{port}")
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,  # 使用从连接字符串中提取的密码
            connect_timeout=3
        )
        conn.close()
        logger.info("MySQL服务器正常运行")
        return True
    except Exception as e:
        logger.error(f"MySQL服务器检查失败: {str(e)}")
        return False

def open_browser(url):
    """在浏览器中打开应用"""
    try:
        # 等待服务器启动
        if wait_for_server(5000):
            webbrowser.open(url)
            logger.info(f"已在默认浏览器中打开应用: {url}")
        else:
            logger.error("服务器未能在预期时间内启动")
    except Exception as e:
        logger.error(f"打开浏览器失败: {str(e)}")

def wait_for_server(port, max_attempts=10, delay=1.0):
    """等待服务器启动"""
    for i in range(max_attempts):
        if is_port_in_use(port):
            logger.info(f"服务器已在端口 {port} 启动")
            return True
        logger.info(f"等待服务器启动... ({i+1}/{max_attempts})")
        time.sleep(delay)
    return False

def init_database():
    """初始化数据库"""
    try:
        # 导入配置和应用
        from config import Config
        from app import create_app, db
        
        # 创建应用
        app = create_app()
        
        # 在应用上下文中初始化数据库
        with app.app_context():
            try:
                # 创建所有表
                db.create_all()
                logger.info("数据库表创建成功")
                
                # 初始化语义库
                from app.models.init_db import init_semantic_library
                init_semantic_library()
                logger.info("语义库初始化成功")
                
                # 检查模型状态
                model_status = app.config.get('MODEL_STATUS', {})
                if model_status:
                    status = model_status.get('status', '未知')
                    story_model = '已加载' if model_status.get('story_model_loaded', False) else '未加载'
                    semantic_model = '已加载' if model_status.get('semantic_model_loaded', False) else '未加载'
                    elapsed_time = model_status.get('elapsed_time', 0)
                    
                    logger.info(f"模型加载状态: {status}")
                    logger.info(f"故事生成模型: {story_model}")
                    logger.info(f"语义标签模型: {semantic_model}")
                    logger.info(f"模型加载耗时: {elapsed_time:.2f}秒")
                else:
                    logger.warning("未找到模型状态信息")
            
            except Exception as e:
                logger.error(f"数据库初始化失败: {str(e)}")
                logger.error(traceback.format_exc())
                print(f"数据库初始化失败: {str(e)}")
                print("\n可能的原因:")
                print("1. MySQL服务未启动")
                print("2. 数据库不存在")
                print("3. 用户名或密码错误")
                print("4. 数据库权限不足")
                print("\n请检查配置文件中的数据库设置。")
                return False
                
        return True
    except Exception as e:
        logger.exception(f"数据库初始化失败: {str(e)}")
        print(f"错误: {str(e)}")
        return False

def handle_db_error():
    """处理数据库错误"""
    print("\n数据库连接错误，请检查:")
    print("1. MySQL服务是否已启动")
    print("2. 配置文件中的数据库连接信息是否正确")
    print("3. 数据库和用户是否存在且有正确的权限")
    print("\n您可以:")
    print("- 启动MySQL服务")
    print("- 创建数据库: CREATE DATABASE semantic_auth;")
    print("- 创建用户并授权: GRANT ALL PRIVILEGES ON semantic_auth.* TO 'root'@'localhost';")
    print("\n详细错误信息请查看日志文件: semantic_auth_app.log")

def main():
    """主函数"""
    try:
        # 检查是否是数据库检查模式
        if len(sys.argv) > 1 and sys.argv[1] == "-c" and len(sys.argv) > 2:
            # 执行指定的检查脚本
            check_script = sys.argv[2]
            logger.info(f"执行检查脚本: {check_script}")
            
            if os.path.exists(check_script):
                # 导入并执行检查脚本
                import importlib.util
                spec = importlib.util.spec_from_file_location("check_module", check_script)
                check_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(check_module)
                
                # 如果脚本有main函数，执行它
                if hasattr(check_module, 'main'):
                    result = check_module.main()
                    if not result:
                        sys.exit(1)
                    sys.exit(0)
            else:
                logger.error(f"检查脚本不存在: {check_script}")
                sys.exit(1)
        
        # 设置工作目录为脚本所在目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件
            app_dir = os.path.dirname(sys.executable)
        else:
            # 如果是普通Python脚本
            app_dir = os.path.dirname(os.path.abspath(__file__))
            
        os.chdir(app_dir)
        logger.info(f"工作目录设置为: {app_dir}")
        
        # 创建必要的目录
        for dir_name in ['user_images', 'uploads', 'uploads/images', 'uploads/texts']:
            os.makedirs(dir_name, exist_ok=True)
            logger.info(f"确保目录存在: {dir_name}")
            
        # 检查MySQL服务器
        if not check_mysql_server():
            logger.error("MySQL服务器检查失败")
            handle_db_error()
            input("按Enter键退出...")
            sys.exit(1)
        
        # 初始化数据库
        if not init_database():
            logger.error("数据库初始化失败")
            handle_db_error()
            input("按Enter键退出...")
            sys.exit(1)
        
        # 导入配置和应用
        from config import Config
        from app import create_app
        
        # 创建应用
        logger.info("创建Flask应用...")
        app = create_app()
        
        # 获取端口
        port = Config.PORT
        logger.info(f"使用端口: {port}")
        
        # 设置要打开的URL
        browser_url = f"http://localhost:{port}"
        
        # 启动浏览器线程
        browser_thread = threading.Timer(2.0, open_browser, [browser_url])
        browser_thread.daemon = True
        browser_thread.start()
        logger.info(f"将在应用启动后自动打开浏览器: {browser_url}")
        
        # 确定是否使用调试模式
        debug_mode = False
        if not getattr(sys, 'frozen', False):  # 如果不是打包的可执行文件
            debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
        
        # 启动Flask应用
        logger.info(f"正在启动Web服务器，调试模式: {debug_mode}...")
        host = '0.0.0.0'  # 在Docker中需要监听所有接口
        port = int(os.environ.get('PORT', 5000))
        debug = os.environ.get('FLASK_ENV') == 'development'
        
        app.run(host=host, port=port, debug=False, use_reloader=False)
        
    except Exception as e:
        logger.exception(f"应用启动时发生错误: {str(e)}")
        print(f"错误: {str(e)}")
        print("\n详细错误信息请查看日志文件: semantic_auth_app.log")
        input("按Enter键退出...")
        sys.exit(1)

if __name__ == "__main__":
    main() 