# 语义认证系统 (Semantic Auth System)

这是一个基于 Python Flask 和 大语言模型 (LLM) 的创新身份验证系统，通过生成和提取语义故事来进行用户认证。

## 🚀 技术栈

- **后端**: Flask 3.0.3, SQLAlchemy, MySQL
- **AI/ML**: 
  - **Qwen1.5-1.8B-Chat**: 用于生成故事。
  - **Chinese-BERT-WWM-Ext**: 用于语义标签提取。
- **图像处理**: OpenCV, Pillow (支持混元DiT及在线API生成认证图片)
- **环境管理**: Conda / Pip

## 🛠️ 核心功能

1. **语义注册**: 用户选择关键词，AI 生成专属故事，并从中提取主体、环境、行为三要素作为语义密码。
2. **多模态认证**: 结合文本故事与生成的图片进行挑战-响应式验证。
3. **安全加固**: 移除硬编码密码，支持 HTTP 基础通信（可扩展 HTTPS），统一日志管理。

## 📦 安装与启动

### 1. 环境准备
```bash
conda create -n flask_env python=3.10
conda activate flask_env
pip install -r requirements.txt
```

### 2. 数据库配置
在 `config.py` 中配置您的 MySQL 连接字符串：
```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://user:password@localhost/db_name'
```

### 3. 运行
```bash
python app_launcher.py
```

## 📝 最近更新
- [2026-03-06] 重构数据库连接方式，统一使用 SQLAlchemy。
- [2026-03-06] 优化 Story Generator 的 Prompt，规范微小说文体。
- [2026-03-06] 扩充 BERT 语义提取的原型词库，提高识别准确率。
- [2026-03-06] 移除所有硬编码敏感信息及冗余的 SSL 配置。

## 📄 开源协议
MIT License
