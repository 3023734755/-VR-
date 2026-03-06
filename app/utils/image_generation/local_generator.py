"""
本地图片生成工具

使用本地模型生成语义认证所需的图片。
支持多种文本到图像模型，包括Hunyuan-DiT等。
"""

import os
import uuid
import torch
import random
import logging
from datetime import datetime
from flask import current_app
from PIL import Image, ImageDraw, ImageFont
import jieba
import jieba.posseg as pseg
from collections import Counter
import warnings

# 设置日志
logger = logging.getLogger(__name__)

# 图片大小设置
IMAGE_WIDTH = 512
IMAGE_HEIGHT = 512

class TextToImageGenerator:
    """文本到图像生成器，支持多种本地模型"""
    
    def __init__(self, model_path=None):
        """
        初始化文本到图像生成器
        
        Args:
            model_path: 模型路径，如果为None则使用配置中的路径
        """
        self.logger = logging.getLogger(__name__)
        self.model_path = model_path or current_app.config.get('MODEL_PATH') or "app/models/hunyuan-dit"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.loaded = False
        
        # 设置随机种子以保持一定的一致性
        random.seed(datetime.now().timestamp())
        
    def load_model(self, use_xformers=True):
        """
        加载模型
        
        Args:
            use_xformers: 是否使用xformers优化内存使用
            
        Returns:
            bool: 成功返回True，失败返回False
        """
        if self.loaded:
            return True
            
        try:
            from diffusers import HunyuanDiTPipeline
            
            self.logger.info(f"正在加载模型: {self.model_path}...")
            
            # 尝试加载模型
            if self.model_path and os.path.exists(self.model_path):
                self.model = HunyuanDiTPipeline.from_pretrained(
                    self.model_path,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
                )
                
                # 移动模型到适当的设备
                self.model = self.model.to(self.device)
                
                # 使用xformers优化内存使用
                if use_xformers and self.device == "cuda":
                    try:
                        self.model.enable_xformers_memory_efficient_attention()
                        self.logger.info("已启用xformers内存优化")
                    except Exception as e:
                        self.logger.warning(f"无法启用xformers: {e}")
                
                self.loaded = True
                self.logger.info(f"模型加载完成，使用设备: {self.device}")
                return True
            else:
                self.logger.error(f"模型路径不存在: {self.model_path}")
                return False
                
        except ImportError as e:
            self.logger.error(f"无法导入所需模块: {e}")
            return False
        except Exception as e:
            self.logger.error(f"加载模型失败: {e}")
            return False
    
    def generate_single_image(self, prompt, output_path=None, negative_prompt=None, steps=30, guidance_scale=7.0):
        """
        生成单张图片
        
        Args:
            prompt: 图像生成提示词
            output_path: 图像输出路径，如果为None则只返回图像对象
            negative_prompt: 负面提示词
            steps: 推理步数
            guidance_scale: 指导尺度
            
        Returns:
            bool | PIL.Image.Image: 如果指定了output_path则返回成功标志，否则返回图像对象
        """
        # 如果模型未加载，尝试加载
        if not self.loaded and not self.load_model():
            # 生成一个占位图像作为替代
            if output_path:
                return self.generate_placeholder_image(prompt, output_path)
            else:
                return Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT))
        
        try:
            # 增强提示词
            semantic_analysis = analyze_prompt_semantics(prompt)
            enhanced_prompt = semantic_analysis["enhanced_prompt"]
            
            # 设置默认的负面提示词
            if negative_prompt is None:
                negative_prompt = "低质量, 模糊, 变形, 扭曲, 糟糕的解剖结构, 错误比例, 低分辨率, 最坏质量"
                
            # 使用模型生成图像
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # 忽略模型的警告
                
                image = self.model(
                    prompt=enhanced_prompt,
                    negative_prompt=negative_prompt,
                    guidance_scale=guidance_scale,
                    num_inference_steps=steps
                ).images[0]
            
            # 如果指定了输出路径，保存图片
            if output_path:
                # 确保目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # 保存图片
                image.save(output_path)
                self.logger.info(f"图片已保存到: {output_path}")
                return True
            else:
                return image
                
        except Exception as e:
            self.logger.error(f"生成图片失败: {str(e)}")
            
            # 如果生成失败，创建一个占位图片
            if output_path:
                return self.generate_placeholder_image(prompt, output_path)
            else:
                placeholder = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), color=(200, 200, 200))
                return placeholder
    
    def generate_placeholder_image(self, prompt, output_path):
        """
        生成占位图片，在模型加载失败或生成错误时使用
        
        Args:
            prompt: 图像生成提示词
            output_path: 图像输出路径
            
        Returns:
            bool: 成功返回True
        """
        try:
            # 创建一个新的白色图片
            image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            
            # 尝试加载字体，如果失败则使用默认字体
            try:
                # 使用系统字体
                font_path = os.path.join(os.environ.get('WINDIR', ''), 'Fonts', 'simhei.ttf')
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 24)
                else:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()
            
            # 绘制文本
            draw.text((50, 50), "图片生成失败", fill=(0, 0, 0), font=font)
            draw.text((50, 100), f"提示词: {prompt[:30]}...", fill=(0, 0, 0), font=font)
            draw.text((50, 150), f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fill=(0, 0, 0), font=font)
            
            # 绘制边框
            draw.rectangle([(0, 0), (IMAGE_WIDTH-1, IMAGE_HEIGHT-1)], outline=(200, 200, 200), width=5)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存图片
            image.save(output_path)
            self.logger.warning(f"已生成占位图片: {output_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"生成占位图片失败: {str(e)}")
            return False

# 语义分析功能，从原image_generator_enhanced.py中提取
def analyze_prompt_semantics(prompt):
    """
    分析提示词的语义结构，提取主体、环境、行为等关键要素
    
    Args:
        prompt: 用户输入的提示词
        
    Returns:
        优化后的提示词，以及语义分析结果
    """
    # 定义常见的停用词
    stopwords = {'的', '了', '是', '在', '和', '与', '或', '这', '那', '我', '你', '他', '她', '它', '们'}
    
    # 语义分类词典 - 扩展并优化词性映射
    semantic_categories = {
        "subject": set([  # 主体 - 人物、实体
            "n", "nr", "nrfg", "nrt", "ns", "nt", "nz",  # 名词类
            "r", "rr", "rz",  # 代词
            "nw",  # 作品名
            "ng",  # 名词性语素
        ]),
        "environment": set([  # 环境 - 场景、时间、地点
            "s", "t", "f",  # 处所词、时间词、方位词
            "a", "ad", "an", "ag",  # 形容词类
            "b", "bl",  # 区别词
            "z",  # 状态词
        ]),
        "behavior": set([  # 行为 - 动作、状态
            "v", "vd", "vn", "vf", "vx", "vi", "vl", "vg",  # 动词类
            "d",  # 副词
            "p",  # 介词
        ])
    }
    
    # 特殊词汇映射 - 直接指定某些常见词的类别
    special_words = {
        # 主体词
        "猎人": "subject", "人": "subject", "男人": "subject", "女人": "subject", "孩子": "subject",
        "动物": "subject", "狗": "subject", "猫": "subject", "鸟": "subject", "马": "subject",
        
        # 环境词
        "森林": "environment", "山": "environment", "海": "environment", "城市": "environment",
        "天空": "environment", "草原": "environment", "沙漠": "environment", "雨": "environment",
        
        # 行为词
        "骑马": "behavior", "奔跑": "behavior", "走": "behavior", "跳": "behavior", "飞": "behavior",
        "看": "behavior", "说": "behavior", "唱": "behavior", "跳舞": "behavior", "思考": "behavior"
    }
    
    # 用于存储分类结果的字典
    categorized = {
        "subject": [],
        "environment": [],
        "behavior": []
    }
    
    # 使用jieba进行词性标注
    words_with_pos = list(pseg.cut(prompt))
    
    # 按语义类别分类词语
    for word, pos in words_with_pos:
        if word in stopwords or len(word) <= 1 and pos not in ["nr", "ns", "nt"]:
            continue
        
        # 首先检查特殊词汇映射
        if word in special_words:
            category = special_words[word]
            categorized[category].append(word)
            continue
        
        # 然后按词性分类
        if pos in semantic_categories["subject"]:
            categorized["subject"].append(word)
        elif pos in semantic_categories["environment"]:
            categorized["environment"].append(word)
        elif pos in semantic_categories["behavior"]:
            categorized["behavior"].append(word)
    
    # 统计各类别词频
    counts = {
        "subject": Counter(categorized["subject"]),
        "environment": Counter(categorized["environment"]),
        "behavior": Counter(categorized["behavior"])
    }
    
    # 提取最重要的词
    top_words = {
        "subject": [word for word, _ in counts["subject"].most_common(2)],
        "environment": [word for word, _ in counts["environment"].most_common(2)],
        "behavior": [word for word, _ in counts["behavior"].most_common(2)]
    }
    
    # 构建语义增强的提示词
    enhanced_prompt = prompt
    
    # 如果提示词太简单（只有几个关键词），构建更丰富的提示词
    if len(prompt.strip()) <= 15 or len(words_with_pos) <= 7:
        # 构建一个更完整的句子
        parts = []
        
        # 添加主体
        if top_words["subject"]:
            parts.append("、".join(top_words["subject"]))
        
        # 添加行为
        if top_words["behavior"]:
            parts.append("正在" + "、".join(top_words["behavior"]))
        
        # 添加环境
        if top_words["environment"]:
            parts.append("在" + "、".join(top_words["environment"]) + "的环境中")
            
        # 如果构建出了新的提示词，使用它
        if parts:
            enhanced_prompt = "，".join(parts)
            
            # 添加一些增强描述，提高画面质量
            enhanced_prompt += "，高清摄影，精致细节，写实风格"
    
    return {
        "original_prompt": prompt,
        "enhanced_prompt": enhanced_prompt,
        "analysis": {
            "subject": categorized["subject"],
            "environment": categorized["environment"],
            "behavior": categorized["behavior"]
        }
    }