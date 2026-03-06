from app import create_app
from app.models.init_db import init_semantic_library
from flask import current_app

if __name__ == "__main__":
    print("开始初始化语义库...")
    app = create_app()
    with app.app_context():
        success = init_semantic_library()
        if success:
            print("语义库初始化成功！")
        else:
            print("语义库初始化失败，请检查日志获取详细信息。") 