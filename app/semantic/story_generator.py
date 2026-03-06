import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
import time
import json
from datetime import datetime
from flask import current_app


class SemanticStoryGenerator:
    def __init__(self, model_path="app/models/Qwen1.5-1.8B-Chat", use_gpu=True):
        """
        初始化语义故事生成器
        """
        self.model_path = model_path
        self.device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        self.tokenizer = None
        self.model = None
        self.loaded = False

        current_app.logger.info(f"故事生成器设备: {self.device}")
        if self.device == "cuda":
            current_app.logger.info(f"GPU: {torch.cuda.get_device_name()}")
            current_app.logger.info(f"显存: {torch.cuda.get_device_properties(0).total_memory / 1024 ** 3:.1f}GB")

    def load_model(self):
        """加载模型和分词器"""
        current_app.logger.info("正在加载故事生成模型...")
        start_time = time.time()

        try:
            # 加载分词器
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True,
                use_fast=True
            )

            # 加载模型
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                use_cache=True
            )

            if self.device == "cpu":
                self.model = self.model.to(self.device)

            # 设置为评估模式
            self.model.eval()

            # 模型预热
            if self.device == "cuda":
                self._warmup_model()

            load_time = time.time() - start_time
            current_app.logger.info(f"故事生成模型加载完成，耗时: {load_time:.2f}秒")
            self.loaded = True
            return True

        except Exception as e:
            current_app.logger.error(f"故事生成模型加载失败: {e}")
            self.loaded = False
            return False

    def _warmup_model(self):
        """模型预热"""
        current_app.logger.info("正在预热故事生成模型...")
        with torch.no_grad():
            dummy_input = self.tokenizer("你好", return_tensors="pt").to(self.device)
            _ = self.model.generate(
                **dummy_input,
                max_new_tokens=10,
                do_sample=False
            )
        current_app.logger.info("故事生成模型预热完成")

    def generate_story(self, prompt, temperature=0.75, top_p=0.85,
                       repetition_penalty=1.15, num_stories=1):
        """
        生成适中长度、有趣且逻辑严密的故事
        """
        if self.model is None or self.tokenizer is None:
            if not self.load_model():
                return []

        # 构建对话格式的提示 - 优化版
        messages = [
            {"role": "system", 
             "content": """你是一位精通微小说创作的文学大师。请严格遵守以下创作规范：
1. 【篇幅限制】：故事长度严格控制在150-200字之间，短小精悍。
2. 【人物设定】：仅限1-2位主角，人物形象鲜明，拒绝群像戏。
3. 【要素完备】：必须包含明确的【主体】（人物/生物）、【环境】（具体场景）和【行为】（核心动作）。
4. 【结构严谨】：
   - 开端：快速交代人物与环境，制造悬念。
   - 发展：情节推进，矛盾升级。
   - 高潮：核心冲突爆发或关键转折。
   - 结局：有余韵的收尾，或反转，或升华。
5. 【文体风格】：叙事流畅，逻辑清晰，拒绝流水账，描写要有画面感。
6. 【主线明确】：围绕一个核心事件展开，不要枝蔓横生。"""},
            {"role": "user", "content": f"请以'{prompt}'为核心元素创作一篇微小说。要求情节生动，人物鲜活，环境描写具有沉浸感，行为逻辑合理。"}
        ]

        stories = []
        current_app.logger.info(f"开始生成 {num_stories} 个故事...")

        for i in range(num_stories):
            current_app.logger.info(f"正在生成第 {i + 1} 个故事...")
            start_time = time.time()

            try:
                # 应用聊天模板
                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
                
                # 编码输入
                inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

                with torch.no_grad():
                    # 生成文本
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=350,  # 足够生成250字左右的故事
                        min_new_tokens=120,  # 确保故事不会太短
                        temperature=temperature,
                        top_p=top_p,
                        do_sample=True,
                        repetition_penalty=repetition_penalty,
                        pad_token_id=self.tokenizer.eos_token_id,
                        eos_token_id=self.tokenizer.eos_token_id,
                        no_repeat_ngram_size=3,  # 避免重复的3-gram
                    )

                # 解码输出
                generated_text = self.tokenizer.decode(
                    outputs[0][inputs['input_ids'].shape[1]:],
                    skip_special_tokens=True
                )

                # 整理故事文本
                story_text = self._process_story_text(generated_text)
                
                generation_time = time.time() - start_time

                story_info = {
                    "story": story_text,
                    "prompt": prompt,
                    "generation_time": f"{generation_time:.2f}秒",
                    "parameters": {
                        "length": len(story_text),
                        "temperature": temperature,
                        "top_p": top_p,
                        "repetition_penalty": repetition_penalty
                    },
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                stories.append(story_info)
                current_app.logger.info(f"第 {i + 1} 个故事生成完成，耗时: {generation_time:.2f}秒，长度: {len(story_text)}字")

            except Exception as e:
                current_app.logger.error(f"生成第 {i + 1} 个故事时出错: {e}")
                import traceback
                current_app.logger.error(traceback.format_exc())
                continue

        current_app.logger.info(f"成功生成 {len(stories)}/{num_stories} 个故事")
        return stories
        
    def _process_story_text(self, text):
        """
        处理生成的故事文本，确保完整性和适当长度
        """
        # 清理文本
        story_text = text.strip()
        
        # 移除可能的角色标识
        role_prefixes = ["助手:", "AI:", "Assistant:", "回答:", "ChatGPT:"]
        for prefix in role_prefixes:
            if story_text.startswith(prefix):
                story_text = story_text[len(prefix):].strip()
        
        # 检查故事是否有结尾
        end_markers = ["。", "！", "？", ".", "!", "?"]
        has_proper_ending = any(story_text.endswith(marker) for marker in end_markers)
        
        # 如果故事太长，智能截断到最近的句号
        if len(story_text) > 300:  # 允许略微超过目标长度
            # 找出所有句号的位置
            sentence_ends = []
            for marker in ["。", "！", "？", ".", "!", "?"]:
                pos = 0
                while True:
                    pos = story_text.find(marker, pos)
                    if pos == -1:
                        break
                    sentence_ends.append(pos)
                    pos += 1
            
            if sentence_ends:
                # 找到最接近250字的句号位置
                sentence_ends.sort()
                best_end = 0
                for end in sentence_ends:
                    if end <= 270:  # 允许略微超过目标长度
                        best_end = end
                    else:
                        break
                
                if best_end > 0:
                    story_text = story_text[:best_end+1]
        
        # 如果故事太短，不做处理，但记录警告
        if len(story_text) < 100:
            current_app.logger.warning(f"生成的故事过短 ({len(story_text)}字)，可能质量不佳")
        
        # 确保故事有结尾标点
        if not has_proper_ending:
            story_text += "。"
            
        return story_text

# 全局实例，延迟初始化
story_generator = None

def get_story_generator():
    """获取故事生成器实例（单例模式）"""
    global story_generator
    if story_generator is None:
        # 从配置中获取模型路径
        model_path = current_app.config.get('STORY_MODEL_PATH', "app/models/Qwen1.5-1.8B-Chat")
        use_gpu = current_app.config.get('USE_GPU', True)
        story_generator = SemanticStoryGenerator(model_path=model_path, use_gpu=use_gpu)
    return story_generator

def generate_stories_from_keywords(keywords, num_stories=1):
    """
    从关键词生成故事
    """
    # 将关键词组合成提示词
    prompt = "、".join(keywords)
    current_app.logger.info(f"使用关键词生成故事: {prompt}")
    
    # 获取故事生成器
    generator = get_story_generator()
    
    # 生成故事
    stories = generator.generate_story(prompt, num_stories=num_stories)
    
    # 记录生成结果
    if stories:
        current_app.logger.info(f"成功生成 {len(stories)} 个故事")
        for i, story in enumerate(stories):
            current_app.logger.info(f"故事 {i+1} 长度: {len(story['story'])}字")
    else:
        current_app.logger.warning("未能生成任何故事")
    
    return stories 