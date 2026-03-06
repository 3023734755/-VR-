from app import create_app, db
from app.models.models import SemanticLibrary
from flask import current_app

if __name__ == "__main__":
    print("正在检查语义库数据...")
    app = create_app()
    with app.app_context():
        total_count = SemanticLibrary.query.count()
        subject_count = SemanticLibrary.query.filter_by(category='subject').count()
        environment_count = SemanticLibrary.query.filter_by(category='environment').count()
        behavior_count = SemanticLibrary.query.filter_by(category='behavior').count()
        other_count = total_count - subject_count - environment_count - behavior_count
        
        print(f"语义库中共有 {total_count} 个语义标签")
        print(f"- 主体语义: {subject_count} 个")
        print(f"- 环境语义: {environment_count} 个")
        print(f"- 行为语义: {behavior_count} 个")
        if other_count > 0:
            print(f"- 未分类语义: {other_count} 个")
            
        # 显示一些示例语义
        print("\n各类别语义示例:")
        
        if subject_count > 0:
            subjects = SemanticLibrary.query.filter_by(category='subject').limit(5).all()
            print("主体语义示例:", ", ".join([s.semantic_text for s in subjects]))
            
        if environment_count > 0:
            environments = SemanticLibrary.query.filter_by(category='environment').limit(5).all()
            print("环境语义示例:", ", ".join([e.semantic_text for e in environments]))
            
        if behavior_count > 0:
            behaviors = SemanticLibrary.query.filter_by(category='behavior').limit(5).all()
            print("行为语义示例:", ", ".join([b.semantic_text for b in behaviors])) 