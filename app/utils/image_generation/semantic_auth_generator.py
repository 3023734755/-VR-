import os
import random
import logging
from flask import current_app
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import shutil

class SemanticAuthImageGenerator:
    """语义认证图片生成工具类，支持在线和本地两种生成方式"""
    
    def __init__(self):
        """初始化语义认证图片生成器"""
        self.logger = logging.getLogger(__name__)
        self.online_generator = None
        self.local_generator = None
        
    def _get_online_generator(self):
        """
        获取在线图片生成器实例
        """
        if self.online_generator is None:
            try:
                self.logger.info("尝试初始化在线图片生成器")
                
                # 检查API密钥是否设置
                api_key = current_app.config.get('DOUBAO_API_KEY')
                if not api_key:
                    self.logger.error("无法初始化在线图片生成器: DOUBAO_API_KEY未在配置中设置")
                    return None
                    
                self.logger.debug(f"使用API密钥: {api_key[:5]}...{api_key[-5:]}")
                
                # 检查API URL是否设置
                api_url = current_app.config.get('DOUBAO_API_URL')
                if not api_url:
                    self.logger.warning("DOUBAO_API_URL未在配置中设置，将使用默认URL")
                else:
                    self.logger.debug(f"使用API URL: {api_url}")
                
                # 导入并初始化在线生成器
                from app.utils.image_generation.online_generator import OnlineImageGenerator
                self.online_generator = OnlineImageGenerator(api_key=api_key)
                self.logger.info("初始化在线图片生成器成功")
            except ImportError as e:
                self.logger.error(f"导入OnlineImageGenerator失败: {str(e)}")
                self.online_generator = None
            except ValueError as e:
                self.logger.error(f"初始化在线图片生成器失败，参数错误: {str(e)}")
                self.online_generator = None
            except Exception as e:
                self.logger.error(f"初始化在线图片生成器失败: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                self.online_generator = None
        return self.online_generator
    
    def _get_local_generator(self):
        """
        获取本地图片生成器实例
        
        Returns:
            TextToImageGenerator: 本地图片生成器实例
        """
        if self.local_generator is None:
            try:
                from app.utils.image_generation.local_generator import TextToImageGenerator
                model_path = current_app.config.get('MODEL_PATH') or "app/models/hunyuan-dit"
                self.local_generator = TextToImageGenerator(model_path=model_path)
                self.logger.info(f"初始化本地图片生成器成功，使用模型: {model_path}")
            except Exception as e:
                self.logger.error(f"初始化本地图片生成器失败: {str(e)}")
                self.local_generator = None
        return self.local_generator
        
    def create_user_image_directory(self, username):
        """
        创建用户图像目录结构
        
        Args:
            username: 用户名
            
        Returns:
            str: 用户图像目录路径
        """
        base_dir = current_app.config.get('USER_IMAGES_FOLDER')
        user_dir = os.path.join(base_dir, username)
        
        # 创建用户目录
        os.makedirs(user_dir, exist_ok=True)
        self.logger.info(f"创建用户图像目录: {user_dir}")
        
        # 创建位置子目录
        semantic_count = current_app.config.get('SEMANTIC_COUNT', 3)
        for i in range(semantic_count):
            pos_dir = os.path.join(user_dir, f"pos{i+1}")
            os.makedirs(pos_dir, exist_ok=True)
            self.logger.info(f"创建位置子目录: {pos_dir}")
        
        return user_dir
    
    def generate_semantic_authentication_images(self, user_id, username, semantic_passwords):
        """
        为用户生成语义认证图片
        
        Args:
            user_id: 用户ID
            username: 用户名
            semantic_passwords: 语义密码列表，每个元素是一个包含position、password_id和companions_ids的dict
            
        Returns:
            dict: 生成结果信息
        """
        from app.models.auth_images import AuthImage
        from app.models.models import SemanticLibrary
        from app import db
        
        try:
            # 创建用户图像目录
            user_dir = self.create_user_image_directory(username)
            
            images_count = 0
            password_images_count = 0
            
            # 对每个语义密码生成图片
            for sp in semantic_passwords:
                position = sp.get('position', 0)
                password_id = sp.get('password_id')
                
                # 获取语义密码的类别
                password_semantic = SemanticLibrary.query.get(password_id)
                if not password_semantic:
                    self.logger.error(f"找不到语义ID: {password_id}")
                    continue
                
                # 创建位置目录
                pos_dir = os.path.join(user_dir, f"pos{position+1}")
                os.makedirs(pos_dir, exist_ok=True)
                
                # 生成包含语义密码的图片 - 每个位置只生成1张包含正确密码的图片
                password_prompt = password_semantic.semantic_text
                
                # 生成密码图片
                img_path = os.path.join(pos_dir, f"password_1.jpg")
                self._generate_image(password_prompt, img_path)
                
                # 记录到数据库
                auth_image = AuthImage.create_from_generated_image(
                    user_id=user_id,
                    position=position,
                    image_path=img_path,
                    semantic1_id=password_id,
                    is_password_image=True
                )
                
                if auth_image:
                    password_images_count += 1
                    images_count += 1
                    self.logger.info(f"为用户 {username} 创建密码图片: {img_path}")
                
                # 生成干扰图片
                # 获取不同于当前语义密码类别的语义
                other_semantics = SemanticLibrary.query.filter(
                    SemanticLibrary.category != password_semantic.category
                ).all()
                
                # 随机选择8个不同类别的语义作为干扰图片
                if len(other_semantics) >= 8:
                    selected_semantics = random.sample(other_semantics, 8)
                else:
                    # 如果不同类别的语义不足8个，可能需要重复使用一些
                    selected_semantics = other_semantics
                    while len(selected_semantics) < 8:
                        selected_semantics.append(random.choice(other_semantics))
                
                # 对每个选择的语义生成一张干扰图片，总共8张
                for i, semantic in enumerate(selected_semantics):
                    distractor_prompt = semantic.semantic_text
                    
                    # 生成干扰图片
                    img_path = os.path.join(pos_dir, f"distractor_{i+1}.jpg")
                    self._generate_image(distractor_prompt, img_path)
                    
                    # 记录到数据库
                    auth_image = AuthImage.create_from_generated_image(
                        user_id=user_id,
                        position=position,
                        image_path=img_path,
                        semantic1_id=semantic.id,
                        is_password_image=False
                    )
                    
                    if auth_image:
                        images_count += 1
                        self.logger.info(f"为用户 {username} 创建干扰图片: {img_path}")
            
            # 返回生成结果
            self.logger.info(f"为用户 {username} 生成了 {images_count} 张图片，其中 {password_images_count} 张密码图片")
            return {
                'success': True,
                'user_id': user_id,
                'username': username,
                'total_images': images_count,
                'password_images': password_images_count
            }
            
        except Exception as e:
            self.logger.error(f"生成语义认证图片失败: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e),
                'user_id': user_id,
                'username': username
            }
    
    def _generate_image(self, prompt, output_path):
        """
        生成图片，优先使用在线生成，失败时回退到本地生成
        
        Args:
            prompt: 图像生成提示词
            output_path: 图像输出路径
            
        Returns:
            bool: 成功返回True
        """
        self.logger.info(f"开始生成图片，提示词: '{prompt[:30]}...'，输出路径: {output_path}")
        
        # 确保输出目录存在
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            self.logger.debug(f"确保输出目录存在: {os.path.dirname(output_path)}")
        except Exception as e:
            self.logger.error(f"创建输出目录失败: {str(e)}")
            return False
        
        # 优先尝试在线生成
        try:
            # 获取在线生成器
            self.logger.info("尝试使用在线API生成图片")
            online_generator = self._get_online_generator()
            if online_generator:
                # 增强提示词，使其更适合生成图片
                enhanced_prompt = f"高质量照片，{prompt}，真实照片风格，清晰细节，自然光照"
                self.logger.debug(f"增强后的提示词: '{enhanced_prompt[:50]}...'")
                
                # 尝试在线生成
                self.logger.info("调用在线API生成图片")
                success, result = online_generator.generate_semantic_authentication_image(enhanced_prompt, output_path)
                if success:
                    self.logger.info(f"使用在线API成功生成图片: {output_path}")
                    return True
                else:
                    self.logger.warning(f"在线API生成图片失败: {result}，尝试使用本地模型")
            else:
                self.logger.warning("在线生成器初始化失败，尝试使用本地模型")
        except Exception as e:
            self.logger.warning(f"在线生成器异常: {str(e)}，尝试使用本地模型")
            import traceback
            self.logger.debug(traceback.format_exc())
        
        # 如果在线生成失败，尝试本地生成
        try:
            # 获取本地生成器
            self.logger.info("尝试使用本地模型生成图片")
            local_generator = self._get_local_generator()
            if local_generator:
                # 尝试本地生成
                self.logger.info("调用本地模型生成图片")
                result = local_generator.generate_single_image(prompt, output_path)
                if result:
                    self.logger.info(f"使用本地模型成功生成图片: {output_path}")
                    return True
                else:
                    self.logger.warning(f"本地模型生成图片失败，使用占位图片")
            else:
                self.logger.warning("本地生成器初始化失败，使用占位图片")
        except Exception as e:
            self.logger.warning(f"本地生成器异常: {str(e)}，使用占位图片")
            import traceback
            self.logger.debug(traceback.format_exc())
        
        # 如果所有方法都失败，使用占位图片
        self.logger.info("所有生成方法都失败，使用占位图片")
        return self._generate_placeholder_image(prompt, output_path)
    
    def _generate_placeholder_image(self, prompt, output_path):
        """
        生成占位图片，用于测试或当其他生成方法失败时
        
        Args:
            prompt: 图像生成提示词
            output_path: 图像输出路径
            
        Returns:
            bool: 成功返回True
        """
        try:
            # 创建一个新的白色图片
            image = Image.new("RGB", (512, 512), color=(240, 240, 240))
            draw = ImageDraw.Draw(image)
            
            # 尝试加载字体，如果失败则使用默认字体
            try:
                # 使用系统字体
                font_path = os.path.join(os.environ.get('WINDIR', ''), 'Fonts', 'simhei.ttf')
                if os.path.exists(font_path):
                    font_large = ImageFont.truetype(font_path, 36)
                    font_small = ImageFont.truetype(font_path, 24)
                else:
                    font_large = ImageFont.load_default()
                    font_small = font_large
            except Exception:
                font_large = ImageFont.load_default()
                font_small = font_large
            
            # 绘制文本
            draw.text((50, 50), f"语义: {prompt}", fill=(0, 0, 0), font=font_large)
            draw.text((50, 150), f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fill=(0, 0, 0), font=font_small)
            
            # 绘制边框
            draw.rectangle([(0, 0), (511, 511)], outline=(0, 0, 0), width=2)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存图片
            image.save(output_path)
            self.logger.info(f"已生成占位图片: {output_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"生成占位图片失败: {str(e)}")
            return False 