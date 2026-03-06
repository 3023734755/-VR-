"""
验证工具模块

用于验证用户输入的各种数据，包括用户名、文件和选择的语义等。
"""

import re
import os
from flask import current_app
from werkzeug.utils import secure_filename

# 支持的文件类型
ALLOWED_TEXT_EXTENSIONS = {'txt', 'doc', 'docx', 'pdf', 'md'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def validate_username(username):
    """
    验证用户名
    
    Args:
        username (str): 用户名
    
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not username:
        return False, "用户名不能为空"
    
    # 去除用户名前后的空白字符
    username = username.strip()
    if not username:
        return False, "用户名不能仅包含空白字符"
    
    if len(username) < 3 or len(username) > 20:
        return False, "用户名长度必须在3-20个字符之间"
    
    # 只允许字母、数字、下划线和中文
    if not re.match(r'^[\w\u4e00-\u9fa5]+$', username):
        return False, "用户名只能包含字母、数字、下划线和中文"
    
    # 检查用户名是否以数字开头
    if re.match(r'^\d', username):
        return False, "用户名不能以数字开头"
    
    # 检查用户名中是否含有特殊关键字
    forbidden_keywords = ['admin', 'root', 'system', 'administrator']
    for keyword in forbidden_keywords:
        if keyword.lower() in username.lower():
            return False, f"用户名不能包含保留字 '{keyword}'"
    
    return True, ""

def validate_file(file):
    """
    验证上传的文件
    
    Args:
        file: 文件对象
    
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not file or not file.filename:
        return False, "未选择文件"
    
    # 安全处理文件名
    original_filename = file.filename
    filename = secure_filename(original_filename)
    
    # 如果安全处理后文件名为空，说明文件名不安全
    if not filename:
        return False, "文件名含有不安全字符"
    
    # 检查文件扩展名
    if '.' not in filename:
        return False, "无效的文件类型，缺少扩展名"
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    # 从配置中获取允许的文件类型（如果可用）
    allowed_text_extensions = current_app.config.get('ALLOWED_TEXT_EXTENSIONS', ALLOWED_TEXT_EXTENSIONS)
    allowed_image_extensions = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', ALLOWED_IMAGE_EXTENSIONS)
    
    if ext not in allowed_text_extensions and ext not in allowed_image_extensions:
        return False, f"不支持的文件类型，允许的类型: {', '.join(allowed_text_extensions.union(allowed_image_extensions))}"
    
    # 检查文件大小
    file.seek(0, 2)  # 移动到文件末尾
    file_size = file.tell()  # 获取文件大小
    file.seek(0)  # 重置文件指针
    
    # 从配置中获取最大文件大小（如果可用）
    max_content_length = current_app.config.get('MAX_CONTENT_LENGTH', MAX_FILE_SIZE)
    
    if file_size > max_content_length:
        return False, f"文件大小超过限制 (最大 {max_content_length // 1024 // 1024}MB)"
    
    # 简单的文件内容检查（防止空文件）
    if file_size == 0:
        return False, "文件不能为空"
    
    # 针对图片的额外验证可以在这里添加（如图片尺寸检查等）
    
    return True, ""

def get_file_type(file):
    """
    获取文件类型，兼容无python-magic的环境
    
    Args:
        file: 文件对象
    
    Returns:
        str: 文件MIME类型
    """
    # 检查是否可以使用python-magic
    if current_app.config.get('USE_MAGIC_LIB', False):
        try:
            import magic
            # 读取文件前1024字节以判断类型
            file_bytes = file.read(1024)
            file.seek(0)  # 重置文件指针
            return magic.from_buffer(file_bytes, mime=True)
        except (ImportError, Exception) as e:
            current_app.logger.warning(f"使用magic库检测文件类型失败: {str(e)}")
    
    # 回退到基于扩展名的检测
    filename = file.filename.lower()
    
    # 文本文件类型
    if filename.endswith(('.txt')):
        return 'text/plain'
    elif filename.endswith(('.doc', '.docx')):
        return 'application/msword'
    elif filename.endswith('.pdf'):
        return 'application/pdf'
    elif filename.endswith('.md'):
        return 'text/markdown'
    
    # 图像文件类型
    elif filename.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    elif filename.endswith('.png'):
        return 'image/png'
    elif filename.endswith('.gif'):
        return 'image/gif'
    elif filename.endswith('.bmp'):
        return 'image/bmp'
    
    # 未知类型
    return 'application/octet-stream'

def is_image_file(file):
    """
    检查是否为图像文件
    
    Args:
        file: 文件对象
    
    Returns:
        bool: 是否为图像文件
    """
    mime_type = get_file_type(file)
    return mime_type.startswith('image/')

def is_text_file(file):
    """
    检查是否为文本文件
    
    Args:
        file: 文件对象
    
    Returns:
        bool: 是否为文本文件
    """
    mime_type = get_file_type(file)
    text_mimes = ['text/', 'application/pdf', 'application/msword']
    return any(mime_type.startswith(prefix) for prefix in text_mimes)

def validate_selected_semantics(selected_semantics, required_count=3):
    """
    验证用户选择的语义
    
    Args:
        selected_semantics (list): 选择的语义列表
        required_count (int): 需要选择的语义数量
    
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not selected_semantics:
        return False, "未选择语义"
    
    # 确保语义是一个列表
    if not isinstance(selected_semantics, list):
        return False, "语义必须以列表形式提供"
    
    # 检查语义数量
    if len(selected_semantics) != required_count:
        return False, f"必须选择 {required_count} 个语义，当前选择了 {len(selected_semantics)} 个"
    
    # 检查是否有重复的语义
    if len(selected_semantics) != len(set(selected_semantics)):
        return False, "不能选择重复的语义"
    
    # 验证每个语义是否为有效的字符串
    for i, semantic in enumerate(selected_semantics):
        if not isinstance(semantic, str):
            return False, f"第 {i+1} 个语义必须是字符串"
        
        if not semantic.strip():
            return False, f"第 {i+1} 个语义不能为空"
        
        # 语义长度检查
        if len(semantic) > 255:
            return False, f"第 {i+1} 个语义过长，最大长度为255个字符"
    
    return True, ""

def validate_text_content(content):
    """
    验证文本内容
    
    Args:
        content (str): 文本内容
    
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not content:
        return False, "文本内容不能为空"
    
    content = content.strip()
    if not content:
        return False, "文本内容不能仅包含空白字符"
    
    # 检查文本长度
    if len(content) < 10:
        return False, "文本内容太短，无法有效提取语义，至少需要10个字符"
    
    # 检查文本是否过长
    max_length = 10000  # 10K字符限制
    if len(content) > max_length:
        return True, f"文本内容将被截断至{max_length}个字符"
    
    return True, ""