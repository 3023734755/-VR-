import os
import time
import json
import requests
import base64
from io import BytesIO
from PIL import Image
import logging
from flask import current_app

class OnlineImageGenerator:
    """使用API在线生成图片的工具类"""
    
    def __init__(self, api_key=None):
        """
        初始化在线图像生成器

        """
        self.logger = logging.getLogger(__name__)
        self.logger.info("初始化在线图像生成器")
        
        # 获取API密钥
        self.api_key = api_key or os.environ.get('DOUBAO_API_KEY') or current_app.config.get('DOUBAO_API_KEY')
        if not self.api_key:
            self.logger.error("API密钥未设置，请在环境变量或配置中设置DOUBAO_API_KEY")
            raise ValueError("API密钥未设置，请在环境变量或配置中设置DOUBAO_API_KEY")
        else:
            self.logger.info(f"API密钥已设置: {self.api_key[:5]}...{self.api_key[-5:]}")
            
        # 获取API URL
        self.api_url = os.environ.get('DOUBAO_API_URL') or current_app.config.get('DOUBAO_API_URL') or "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        self.logger.info(f"使用API URL: {self.api_url}")
        
        # 获取模型版本
        self.model_version = os.environ.get('DOUBAO_MODEL_VERSION') or current_app.config.get('DOUBAO_MODEL_VERSION') or "doubao-seedream-3-0-t2i-250415"
        self.logger.info(f"使用模型版本: {self.model_version}")
        
        # 获取水印设置
        self.disable_watermark = os.environ.get('DISABLE_WATERMARK', 'True').lower() in ('true', '1', 't') or current_app.config.get('DISABLE_WATERMARK', True)
        self.logger.info(f"水印禁用状态: {self.disable_watermark}")
        
        # 测试API连接
        try:
            self.logger.info("测试API连接...")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            response = requests.head(self.api_url, headers=headers, timeout=5)
            if response.status_code == 405:  # HEAD方法通常不被支持，但不是404
                self.logger.info("API连接测试成功")
            elif response.status_code == 404:
                self.logger.warning(f"API URL可能不正确: {self.api_url}, 状态码: {response.status_code}")
            else:
                self.logger.info(f"API连接测试返回状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"API连接测试失败: {str(e)}")
        except Exception as e:
            self.logger.warning(f"API连接测试过程中发生未知错误: {str(e)}")
        
        self.logger.info("在线图像生成器初始化完成")
    
    def generate_image(self, prompt, negative_prompt=None, size="1024x1024", output_path=None):
        """
        使用API生成图片
        """
        try:
            # 解析尺寸
            width, height = map(int, size.split('x'))
            
            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 构建请求体
            payload = {
                "model": self.model_version,
                "prompt": prompt,
                "n": 1,
                "response_format": "url",  # 使用URL格式获取图片
                "size": size,
                "watermark": not self.disable_watermark  # 当disable_watermark为True时，watermark设为False
            }
            
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt
                
            self.logger.info(f"正在使用API生成图片: '{prompt}'")
            
            # 发送请求到豆包API
            response = requests.post(self.api_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                self.logger.error(f"API调用失败: {response.status_code} - {response.text}")
                return False, f"API调用失败: {response.status_code} - {response.text}"
                
            response_data = response.json()
            self.logger.debug(f"API响应: {json.dumps(response_data, ensure_ascii=False)}")
            
            # 解析并保存图片
            if "data" in response_data and len(response_data["data"]) > 0:
                image_data = response_data["data"][0]
                
                if "url" in image_data:
                    # 从URL获取图片
                    image_url = image_data["url"]
                    self.logger.info(f"获取到图片URL: {image_url}")
                    
                    # 下载图像
                    img_response = requests.get(image_url)
                    if img_response.status_code != 200:
                        self.logger.error(f"下载图片失败: HTTP {img_response.status_code}")
                        return False, f"下载图片失败: HTTP {img_response.status_code}"
                    
                    image = Image.open(BytesIO(img_response.content))
                    
                    # 如果提供了输出路径，保存图片
                    if output_path:
                        # 确保目录存在
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        
                        # 保存图片
                        image.save(output_path)
                        self.logger.info(f"图片已保存到: {output_path}")
                        
                        return True, output_path
                    else:
                        return True, image
                    
                elif "b64_json" in image_data:
                    # 从Base64解码图片
                    image_bytes = base64.b64decode(image_data["b64_json"])
                    image = Image.open(BytesIO(image_bytes))
                    
                    # 如果提供了输出路径，保存图片
                    if output_path:
                        # 确保目录存在
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        
                        # 保存图片
                        image.save(output_path)
                        self.logger.info(f"图片已保存到: {output_path}")
                        
                        return True, output_path
                    else:
                        return True, image
                else:
                    self.logger.error("API响应中未找到图片数据")
                    return False, "API响应中未找到图片数据"
            else:
                self.logger.error(f"API响应格式不正确: {response_data}")
                return False, f"API响应格式不正确: {response_data}"
                
        except Exception as e:
            self.logger.error(f"在线图片生成失败: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False, f"图片生成失败: {str(e)}"
    
    def generate_semantic_authentication_image(self, semantic_prompt, output_path):
        """
        生成语义认证图片
        """
        # 为语义认证场景优化的提示词
        enhanced_prompt = f"高质量照片，{semantic_prompt}，真实风格，清晰细节，自然光照"

        negative_prompt = "模糊, 变形, 低分辨率, 错误比例, 水印, 文字, 签名, 裸露, 暴力"
        
        return self.generate_image(
            prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
            size="1024x1024",
            output_path=output_path
        )
    
    def generate_batch_authentication_images(self, semantic_prompts, output_dir, prefix="img"):
        """
        批量生成认证图片
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        results = {
            "success": [],
            "failed": [],
            "total": len(semantic_prompts)
        }
        
        for i, prompt in enumerate(semantic_prompts):
            # 构建输出路径
            output_path = os.path.join(output_dir, f"{prefix}_{i+1}.jpg")
            
            # 生成图片
            success, result = self.generate_semantic_authentication_image(prompt, output_path)
            
            if success:
                results["success"].append({
                    "prompt": prompt,
                    "path": output_path
                })
            else:
                results["failed"].append({
                    "prompt": prompt,
                    "error": result
                })

            time.sleep(0.5)
        
        return results 