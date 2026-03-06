"""
文件处理工具模块

用于处理上传的文件，包括文件类型检测、安全存储和格式转换等功能。
"""

import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app
import mimetypes
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 尝试导入magic库，用于文件类型检测
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logger.warning("python-magic库未安装，将使用基本方法进行文件类型检测")

# 尝试导入PIL库，用于图像处理
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL库未安装，图像处理功能将受限")

# 支持的文件类型
ALLOWED_TEXT_EXTENSIONS = {'txt', 'doc', 'docx', 'pdf', 'md'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

def get_file_type(file):
    """
    检测文件类型
    
    Args:
        file: 文件对象
    
    Returns:
        str: 文件类型 ('text', 'image' 或 'unknown')
    """
    # 检查是否可以使用python-magic
    if current_app.config.get('USE_MAGIC_LIB', False) and MAGIC_AVAILABLE:
        try:
            # 读取文件前1024字节以判断类型
            file_bytes = file.read(1024)
            file.seek(0)  # 重置文件指针
            
            # 使用python-magic检测MIME类型
            mime = magic.Magic(mime=True)
            mime_type = mime.from_buffer(file_bytes)
            
            if mime_type.startswith('text/') or mime_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                return 'text'
            elif mime_type.startswith('image/'):
                return 'image'
        except Exception as e:
            current_app.logger.error(f"使用magic库检测文件类型失败: {str(e)}")
    
    # 回退到基于扩展名的检测
    filename = file.filename.lower()
    
    # 通过文件扩展名判断
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1]
        if ext in ALLOWED_TEXT_EXTENSIONS:
            return 'text'
        elif ext in ALLOWED_IMAGE_EXTENSIONS:
            return 'image'
    
    # 如果magic库不可用且无法通过扩展名判断，尝试使用mimetypes库
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        if mime_type.startswith('text/') or mime_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return 'text'
        elif mime_type.startswith('image/'):
            return 'image'
    
    return 'unknown'

def get_file_type_from_path(file_path):
    """
    根据文件路径判断文件类型
    
    Args:
        file_path (str): 文件路径
    
    Returns:
        str: 文件类型 ('text', 'image' 或 'unknown')
    """
    if not file_path or not os.path.exists(file_path):
        return 'unknown'
    
    # 检查是否可以使用python-magic
    if current_app and current_app.config.get('USE_MAGIC_LIB', False) and MAGIC_AVAILABLE:
        try:
            # 使用python-magic检测MIME类型
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(file_path)
            
            if mime_type.startswith('text/') or mime_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                return 'text'
            elif mime_type.startswith('image/'):
                return 'image'
        except Exception as e:
            if current_app:
                current_app.logger.error(f"使用magic库检测文件类型失败: {str(e)}")
    
    # 回退到基于扩展名的检测
    _, ext = os.path.splitext(file_path)
    ext = ext.lower().lstrip('.')
    
    # 通过扩展名判断
    if ext in ALLOWED_TEXT_EXTENSIONS:
        return 'text'
    elif ext in ALLOWED_IMAGE_EXTENSIONS:
        return 'image'
    
    # 如果magic库不可用且无法通过扩展名判断，尝试使用mimetypes库
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        if mime_type.startswith('text/') or mime_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return 'text'
        elif mime_type.startswith('image/'):
            return 'image'
    
    return 'unknown'

def save_file(file, file_type):
    """
    安全地保存文件
    
    Args:
        file: 文件对象
        file_type: 文件类型 ('text' 或 'image')
    
    Returns:
        str: 保存的文件路径
    """
    if not file or not file.filename:
        return None
    
    filename = secure_filename(file.filename)
    
    # 生成唯一文件名
    unique_filename = f"{uuid.uuid4()}_{filename}"
    
    # 根据文件类型选择保存目录
    if file_type == 'text':
        save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'texts')
    elif file_type == 'image':
        save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'images')
    else:
        return None
    
    # 确保目录存在
    os.makedirs(save_dir, exist_ok=True)
    
    # 保存文件
    file_path = os.path.join(save_dir, unique_filename)
    file.save(file_path)
    
    return file_path

def extract_text_from_file(file_path):
    """
    从文件中提取文本内容
    
    Args:
        file_path: 文件路径
    
    Returns:
        str: 提取的文本内容
    """
    try:
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # 纯文本文件
        if ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        
        # PDF文件
        elif ext == '.pdf':
            try:
                from pdfminer.high_level import extract_text
                return extract_text(file_path)
            except ImportError:
                logger.warning("pdfminer not installed, cannot extract text from PDF")
        
        # Word文档
        elif ext in ['.doc', '.docx']:
            try:
                import docx
                doc = docx.Document(file_path)
                return '\n'.join([para.text for para in doc.paragraphs])
            except ImportError:
                logger.warning("python-docx not installed, cannot extract text from Word documents")
        
    except Exception as e:
        logger.error(f"Error extracting text from file: {str(e)}")
    
    return None
