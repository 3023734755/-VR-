import os
import shutil
import sys

def create_directories():
    """创建必要的目录"""
    try:
        os.makedirs('dist/SemanticAuthApp/jaraco/text', exist_ok=True)
        print("✓ 已创建 jaraco 目录结构")
    except Exception as e:
        print(f"✗ 创建目录失败: {str(e)}")

def create_init_files():
    """创建 __init__.py 文件"""
    try:
        with open('dist/SemanticAuthApp/jaraco/__init__.py', 'w', encoding='utf-8') as f:
            pass
        with open('dist/SemanticAuthApp/jaraco/text/__init__.py', 'w', encoding='utf-8') as f:
            pass
        print("✓ 已创建 __init__.py 文件")
    except Exception as e:
        print(f"✗ 创建 __init__.py 文件失败: {str(e)}")

def create_batch_file():
    """创建启动批处理文件"""
    batch_content = '''@echo off
echo ====================================
echo      语义认证应用启动器
echo ====================================
echo 请确保 MySQL 服务已启动。
echo.

cd /d "%~dp0"
echo 正在启动应用程序...
start /b SemanticAuthApp.exe

echo.
echo 如果应用未自动打开浏览器，请手动访问：http://localhost:5000
echo.
echo 注意: 请保持此窗口打开，关闭窗口将终止应用程序。
echo ====================================
pause
'''
    try:
        with open('dist/SemanticAuthApp/启动应用.bat', 'w', encoding='utf-8') as f:
            f.write(batch_content)
        print("✓ 已创建启动批处理文件")
    except Exception as e:
        print(f"✗ 创建启动批处理文件失败: {str(e)}")

def create_readme():
    """创建 README 文件"""
    readme_content = '''语义认证应用使用说明
====================================

一、启动应用
1. 确保 MySQL 服务已启动
2. 双击"启动应用.bat"文件
3. 应用将自动在浏览器中打开，地址为 http://localhost:5000

二、常见问题
1. 如果应用无法启动，请检查日志文件夹中的日志
2. 如果浏览器未自动打开，请手动访问 http://localhost:5000
3. 如果出现"无法连接到服务器"错误，请确保应用正在运行且没有被防火墙阻止

三、故障排除
1. 检查 logs 文件夹中的日志文件
2. 确保所有必要的目录和文件都存在
3. 确保 MySQL 服务正在运行

四、联系支持
如有任何问题，请联系技术支持。
'''
    try:
        with open('dist/SemanticAuthApp/README.txt', 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print("✓ 已创建 README 文件")
    except Exception as e:
        print(f"✗ 创建 README 文件失败: {str(e)}")

def ensure_logs_directory():
    """确保日志目录存在"""
    try:
        os.makedirs('dist/SemanticAuthApp/logs', exist_ok=True)
        print("✓ 已创建日志目录")
    except Exception as e:
        print(f"✗ 创建日志目录失败: {str(e)}")

def main():
    print("\n===== 开始执行打包后处理 =====")
    create_directories()
    create_init_files()
    create_batch_file()
    create_readme()
    ensure_logs_directory()
    print("===== 打包后处理完成 =====\n")
    print("应用已打包到 dist/SemanticAuthApp 目录")
    print("可以通过运行 dist/SemanticAuthApp/启动应用.bat 来启动应用")

if __name__ == "__main__":
    main()