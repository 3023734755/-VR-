from flask import Blueprint, jsonify, request, render_template, current_app
from app.utils.semantic_utils import (
    get_semantic_by_category, 
    get_random_semantics_by_category,
    get_all_semantics,
    search_semantics,
    get_semantic_stats
)
from app.semantic.semantic_labeler import extract_labels_from_text
from app.semantic.story_generator import generate_stories_from_keywords

# 创建蓝图
semantic_bp = Blueprint('semantic', __name__, url_prefix='/semantic')

@semantic_bp.route('/stats', methods=['GET'])
def stats():
    """获取语义库统计信息"""
    stats = get_semantic_stats()
    return jsonify(stats)

@semantic_bp.route('/all', methods=['GET'])
def all_semantics():
    """获取所有语义标签"""
    semantics = get_all_semantics()
    return jsonify(semantics)

@semantic_bp.route('/category/<category>', methods=['GET'])
def by_category(category):
    """按类别获取语义标签"""
    limit = request.args.get('limit', type=int)
    random_select = request.args.get('random', '0') == '1'
    
    if category not in ['subject', 'environment', 'behavior']:
        return jsonify({'error': '无效的类别'}), 400
        
    semantics = get_semantic_by_category(category, limit, random_select)
    return jsonify(semantics)

@semantic_bp.route('/random/<category>/<int:count>', methods=['GET'])
def random_semantics(category, count):
    """随机获取指定类别的语义标签"""
    if category not in ['subject', 'environment', 'behavior']:
        return jsonify({'error': '无效的类别'}), 400
        
    if count < 1 or count > 100:
        return jsonify({'error': '数量必须在1-100之间'}), 400
        
    semantics = get_random_semantics_by_category(category, count)
    return jsonify(semantics)

@semantic_bp.route('/search', methods=['GET'])
def search():
    """搜索语义标签"""
    query = request.args.get('q', '')
    category = request.args.get('category')
    limit = request.args.get('limit', 10, type=int)
    
    if not query:
        return jsonify({'error': '搜索关键词不能为空'}), 400
        
    if category and category not in ['subject', 'environment', 'behavior']:
        return jsonify({'error': '无效的类别'}), 400
        
    semantics = search_semantics(query, category, limit)
    return jsonify(semantics)

@semantic_bp.route('/dashboard', methods=['GET'])
def dashboard():
    """语义标签仪表盘页面"""
    stats = get_semantic_stats()
    return render_template('semantic/dashboard.html', stats=stats)

# 在应用程序中注册蓝图的函数
def register_semantic_routes(app):
    app.register_blueprint(semantic_bp)
    
    # 提取语义标签
    @app.route('/api/extract_semantics', methods=['POST'])
    def extract_semantics():
        """从文本中提取语义标签"""
        data = request.json
        if not data or 'text' not in data:
            return jsonify({'error': 'Missing text parameter'}), 400
            
        text = data['text']
        num_per_category = data.get('num_per_category', 3)
        
        try:
            # 提取语义标签
            labels = extract_labels_from_text(text, num_per_category)
            return jsonify(labels)
        except Exception as e:
            current_app.logger.error(f"提取语义标签时出错: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    # 生成故事
    @app.route('/api/generate_story', methods=['POST'])
    def generate_story():
        """根据关键词生成故事"""
        data = request.json
        if not data or 'keywords' not in data:
            return jsonify({'error': 'Missing keywords parameter'}), 400
            
        keywords = data['keywords']
        num_stories = data.get('num_stories', 1)
        
        try:
            # 生成故事
            stories = generate_stories_from_keywords(keywords, num_stories)
            return jsonify(stories)
        except Exception as e:
            current_app.logger.error(f"生成故事时出错: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    # 获取模型状态
    @app.route('/api/model_status', methods=['GET'])
    def get_model_status():
        """获取模型状态"""
        try:
            # 从应用配置中获取模型状态
            model_status = current_app.config.get('MODEL_STATUS', {})
            
            # 如果没有预热状态，从当前状态获取
            if not model_status:
                from app.semantic.story_generator import get_story_generator
                from app.semantic.semantic_labeler import bert_model
                
                story_gen = get_story_generator()
                story_model_loaded = hasattr(story_gen, 'model') and story_gen.model is not None
                semantic_model_loaded = bert_model is not None
                
                model_status = {
                    "status": "成功" if story_model_loaded and semantic_model_loaded else 
                              "部分成功" if story_model_loaded or semantic_model_loaded else "失败",
                    "story_model_loaded": story_model_loaded,
                    "semantic_model_loaded": semantic_model_loaded,
                    "elapsed_time": 0  # 无法获取耗时
                }
            
            # 添加当前时间戳
            import time
            model_status["timestamp"] = time.time()
            
            return jsonify(model_status)
        except Exception as e:
            current_app.logger.error(f"获取模型状态时出错: {str(e)}")
            return jsonify({
                'error': str(e),
                'status': '失败',
                'story_model_loaded': False,
                'semantic_model_loaded': False
            }), 500 