"""
HTTP通信工具模块

用于处理HTTP请求和响应，包括请求验证、响应格式化等。
"""

import json
import logging
from flask import request, jsonify
from functools import wraps

logger = logging.getLogger(__name__)

def format_response(success=True, message="", data=None, status_code=200):
    """
    格式化API响应
    
    Args:
        success (bool): 请求是否成功
        message (str): 响应消息
        data (dict): 响应数据
        status_code (int): HTTP状态码
    
    Returns:
        tuple: (响应数据, HTTP状态码)
    """
    response = {
        "success": success,
        "message": message
    }
    
    if data is not None:
        response["data"] = data
    
    return jsonify(response), status_code

def validate_json_request(required_fields=None):
    """
    验证JSON请求装饰器
    
    Args:
        required_fields (list): 必需的字段列表
    
    例子:
        @validate_json_request(['username', 'content'])
        def some_route():
            # 处理请求
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 验证内容类型
            if not request.is_json and not request.form:
                return format_response(
                    success=False,
                    message="请求必须是JSON或表单数据",
                    status_code=400
                )
            
            # 获取数据
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form
            
            # 验证必需字段
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return format_response(
                        success=False,
                        message=f"缺少必需字段: {', '.join(missing_fields)}",
                        status_code=400
                    )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def parse_request():
    """
    解析HTTP请求
    
    处理请求，支持JSON和表单数据
    
    Returns:
        dict: 请求数据
    """
    if request.is_json:
        return request.get_json()
    elif request.form:
        # 处理表单数据
        data = {}
        for key in request.form:
            data[key] = request.form[key]
        
        # 处理文件
        if request.files:
            # 处理上传的文件
            for key in request.files:
                if request.files[key]:
                    data[key] = request.files[key]
        
        return data
    
    # 如果既不是JSON也不是表单数据，返回空字典
    return {}

def log_request(include_body=False):
    """
    记录API请求的装饰器
    
    Args:
        include_body (bool): 是否包含请求体
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 记录基本请求信息
            logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")
            
            # 如果需要，记录请求体
            if include_body and request.is_json:
                logger.debug(f"Request body: {json.dumps(request.get_json())}")
            
            # 执行原函数
            return f(*args, **kwargs)
        return decorated_function
    return decorator
