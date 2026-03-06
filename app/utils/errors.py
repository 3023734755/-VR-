"""
错误处理模块

用于注册和处理应用中的各种错误。
"""

from flask import jsonify

def register_error_handlers(app):
    """
    注册全局错误处理函数
    
    Args:
        app: Flask应用实例
    """
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request', 'message': str(error)}), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized', 'message': str(error)}), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden', 'message': str(error)}), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found', 'message': str(error)}), 404
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({'error': 'Request entity too large', 'message': '上传的文件超过大小限制'}), 413
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({'error': 'Internal server error', 'message': str(error)}), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """处理未捕获的异常"""
        app.logger.error(f"Unhandled exception: {str(error)}")
        return jsonify({
            'error': 'Internal server error',
            'message': '服务器内部错误，请稍后再试'
        }), 500
