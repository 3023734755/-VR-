import os
import shutil
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('model_removal.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('model_removal')


def remove_models():
    """删除打包文件中的大型模型文件"""
    # 打包目录路径
    dist_dir = 'E:/python/flaskProject3/dist/SemAuth'

    # 模型目录路径（在打包文件中）
    model_paths = [
        '_internal/app/models/chinese-bert-wwm-ext',
        '_internal/app/models/hunyuan-dit',
        '_internal/app/models/Qwen1.5-1.8B-Chat'
    ]

    total_saved = 0

    for model_path in model_paths:
        full_path = os.path.join(dist_dir, model_path)
        if os.path.exists(full_path):
            # 计算目录大小
            dir_size = 0
            for path, dirs, files in os.walk(full_path):
                for f in files:
                    fp = os.path.join(path, f)
                    if os.path.exists(fp):
                        dir_size += os.path.getsize(fp)

            # 转换为MB
            dir_size_mb = dir_size / (1024 * 1024)

            # 删除目录
            try:
                shutil.rmtree(full_path)
                logger.info(f"已删除模型: {model_path} (节省约 {dir_size_mb:.2f} MB)")
                total_saved += dir_size_mb

                # 创建占位文件夹
                os.makedirs(full_path, exist_ok=True)

                # 创建README文件，说明如何下载模型
                readme_content = f"""# 模型文件已移除

此目录原本包含 {os.path.basename(model_path)} 模型文件，但为了减小打包体积，这些文件已被移除。

## 如何获取模型文件

请通过以下方式获取模型文件：

1. 访问 Hugging Face 模型库: https://huggingface.co/models
2. 搜索 "{os.path.basename(model_path)}"
3. 下载模型文件
4. 将下载的文件放置在此目录中

或者运行应用程序的自动下载功能:
1. 首次启动应用程序时，会提示下载缺失的模型文件
2. 按照提示操作，等待下载完成

## 所需文件

请确保下载完整的模型文件，包括:
- 模型权重文件 (*.bin, *.safetensors)
- 配置文件 (config.json)
- 分词器文件 (tokenizer.json, vocab.txt)
"""

                with open(os.path.join(full_path, 'README.md'), 'w', encoding='utf-8') as f:
                    f.write(readme_content)

            except Exception as e:
                logger.error(f"删除模型时出错 {model_path}: {str(e)}")
        else:
            logger.warning(f"模型路径不存在: {full_path}")

    logger.info(f"总共节省空间: 约 {total_saved:.2f} MB ({total_saved / 1024:.2f} GB)")


if __name__ == "__main__":
    logger.info("开始删除大型模型文件...")
    remove_models()
    logger.info("模型文件删除完成")