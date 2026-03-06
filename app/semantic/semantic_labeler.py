import os
import jieba
import jieba.posseg as pseg
from collections import Counter
from flask import current_app
import logging

# 设置jieba日志级别
jieba.setLogLevel(logging.INFO)

# 全局变量，用于存储加载的语义模型
bert_model = None
bert_tokenizer = None

class ChineseSemanticLabeler:
    """
    中文语义标签提取器
    使用chinese-bert-wwm-ext模型和规则结合的方式提取文本中的语义标签
    """
    def __init__(self, model_path=None):
        self.stopwords = set()  # 停用词集合
        self.special_words = {}  # 特殊词汇映射: {词: 类别}
        
        # 词性分类映射
        self.semantic_categories = {
            "subject": {'n', 'nr', 'nrfg', 'nrt', 'ns', 'nt', 'nz', 'vn', 'an'},  # 主体相关词性
            "environment": {'ns', 's', 'f', 'n'},  # 环境相关词性
            "behavior": {'v', 'vd', 'vg', 'vn', 'vi', 'vl', 'vf'}   # 行为相关词性
        }
        
        # 加载停用词
        self._load_stopwords()
        
        # 加载特殊词汇映射
        self._load_special_words()
    
    def _load_stopwords(self):
        """加载停用词"""
        try:
            # 获取停用词文件路径
            base_dir = os.path.dirname(os.path.dirname(__file__))
            stopwords_file = os.path.join(base_dir, 'resources', 'stopwords.txt')
            
            # 如果文件存在，加载停用词
            if os.path.exists(stopwords_file):
                with open(stopwords_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        word = line.strip()
                        if word:
                            self.stopwords.add(word)
                current_app.logger.info(f"已加载 {len(self.stopwords)} 个停用词")
            else:
                current_app.logger.warning(f"停用词文件不存在: {stopwords_file}")
                # 添加一些基本的停用词
                self.stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
                             '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会',
                             '着', '没有', '看', '好', '自己', '这'}
        except Exception as e:
            current_app.logger.error(f"加载停用词时出错: {str(e)}")
            # 添加一些基本的停用词作为备用
            self.stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都'}
    
    def _load_special_words(self):
        """加载特殊词汇映射"""
        try:
            # 加载语义词库中的词汇作为特殊词汇
            from app.models.models import SemanticLibrary
            
            # 查询所有分类的语义词汇
            semantics = SemanticLibrary.query.all()
            
            # 构建特殊词汇映射
            for semantic in semantics:
                if semantic.category in ['subject', 'environment', 'behavior']:
                    self.special_words[semantic.semantic_text] = semantic.category
            
            current_app.logger.info(f"已加载 {len(self.special_words)} 个特殊词汇")
        except Exception as e:
            current_app.logger.error(f"加载特殊词汇映射时出错: {str(e)}")
            # 如果数据库访问失败，使用默认的特殊词汇
            self.special_words = {}
    
    def extract_labels(self, text, num_labels_per_category=3):
        """
        从文本中提取语义标签
        """
        try:
            global bert_model, bert_tokenizer
            
            # 使用基于规则的方法提取候选标签
            rule_based_labels = self._extract_by_rules(text)
            
            # 如果BERT模型已加载，使用模型进行标签提取
            if bert_model is not None and bert_tokenizer is not None:
                # 使用BERT模型提取语义标签并与基于规则的结果合并
                model_based_labels = self._extract_by_model(text)
                
                # 合并两种结果
                for category in ["subject", "environment", "behavior"]:
                    rule_words = {item[0] for item in rule_based_labels[category]}
                    for label, score in model_based_labels[category]:
                        if label not in rule_words:
                            rule_based_labels[category].append((label, score * 0.8))  # 模型权重稍低
            
            # 获取每个类别的前N个标签
            result = {}
            for category in ["subject", "environment", "behavior"]:
                # 按权重排序
                sorted_labels = sorted(rule_based_labels[category], key=lambda x: x[1], reverse=True)
                # 获取前N个标签，但不重复
                unique_labels = []
                seen = set()
                for label, score in sorted_labels:
                    if label not in seen and len(unique_labels) < num_labels_per_category:
                        unique_labels.append({"text": label, "score": score})
                        seen.add(label)
                result[category] = unique_labels
            
            return result
        
        except Exception as e:
            current_app.logger.error(f"提取语义标签时出错: {str(e)}")
            import traceback
            current_app.logger.error(traceback.format_exc())
            # 出错时返回空结果
            return {
                "subject": [],
                "environment": [],
                "behavior": []
            }
    
    def _extract_by_rules(self, text):
        """
        """
        # 分割文本为句子
        sentences = self._split_sentences(text)
        
        # 初始化计数器
        category_counters = {
            "subject": Counter(),
            "environment": Counter(),
            "behavior": Counter()
        }
        
        # 直接对整个文本进行特殊词汇匹配
        words = jieba.cut(text)
        for word in words:
            if word in self.special_words and word not in self.stopwords:
                category = self.special_words[word]
                # 特殊词汇给予更高权重
                category_counters[category][word] += 3
        
        # 如果没有有效句子，直接对整个文本进行分析
        if not sentences:
            categorized_words = self._extract_pos_words(text)
            for category in ["subject", "environment", "behavior"]:
                for word, _ in categorized_words[category]:
                    if word not in self.stopwords:
                        category_counters[category][word] += 1
        
        # 对每个句子进行分析
        for i, sentence in enumerate(sentences):
            # 句子位置权重：首尾句权重较高
            position_weight = 1.2 if i == 0 or i == len(sentences) - 1 else 1.0
            
            # 基于词性的分类
            categorized_words = self._extract_pos_words(sentence)
            
            # 基于句子结构的语义分析
            sentence_semantics = self._analyze_sentence_semantics(sentence)
            
            # 合并两种分析结果
            for category in ["subject", "environment", "behavior"]:
                # 从词性分析中获取词汇
                for word, _ in categorized_words[category]:
                    if word not in self.stopwords:
                        category_counters[category][word] += 1 * position_weight
                
                # 从句子结构分析中获取词汇
                for word, weight in sentence_semantics[category]:
                    if word not in self.stopwords:
                        # 结构分析权重更高，并考虑句子位置
                        category_counters[category][word] += weight * position_weight
        
        # 转换为(word, weight)的元组列表
        result = {}
        for category, counter in category_counters.items():
            result[category] = counter.most_common()
        
        return result
    
    def _extract_by_model(self, text):
        """
        使用BERT模型提取语义标签
        """
        global bert_model, bert_tokenizer
        
        try:
            import torch
            from torch.nn import functional as F
            
            # 将文本转换为模型输入
            inputs = bert_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            
            # 获取BERT的输出
            with torch.no_grad():
                outputs = bert_model(**inputs)
            
            # 获取[CLS]标记的输出，这代表整个序列的语义表示
            cls_output = outputs.last_hidden_state[:, 0, :]
            
            # 获取词元的隐藏状态
            token_outputs = outputs.last_hidden_state[0]
            
            # 将每个词的表示与类别表示比较，计算相似度
            result = {
                "subject": [],
                "environment": [],
                "behavior": []
            }
            
            # 获取特殊词语义
            subject_embeddings = []
            environment_embeddings = []
            behavior_embeddings = []
            
            # 扩充并优化类别原型词库，提高语义匹配的覆盖面和准确性
            subject_words = [
                "人", "男人", "女人", "老人", "小孩", "学生", "老师", "医生", "警察", "战士", 
                "科学家", "艺术家", "工人", "农民", "宇航员", "机器人", "外星人", "神仙", "妖怪",
                "猫", "狗", "鸟", "鱼", "狮子", "老虎", "大象", "恐龙", "巨龙"
            ]
            environment_words = [
                "森林", "草原", "沙漠", "海洋", "高山", "峡谷", "岛屿", "极地", "天空", "太空",
                "城市", "乡村", "街道", "广场", "公园", "学校", "医院", "工厂", "商店", "餐厅",
                "房间", "卧室", "客厅", "厨房", "书房", "办公室", "实验室", "图书馆", "博物馆",
                "废墟", "古堡", "神庙", "地牢", "战场", "舞台", "梦境", "幻境"
            ]
            behavior_words = [
                "走路", "跑步", "跳跃", "攀爬", "游泳", "飞行", "驾驶", "骑行", "旅行", "探险",
                "说话", "喊叫", "唱歌", "哭泣", "大笑", "思考", "观察", "寻找", "发现", "研究",
                "工作", "学习", "创作", "建造", "修理", "破坏", "战斗", "攻击", "防御", "逃跑",
                "吃饭", "睡觉", "休息", "玩耍", "拥抱", "亲吻", "帮助", "伤害", "拯救", "毁灭"
            ]            
            # 计算类别原型嵌入
            for word in subject_words:
                inputs = bert_tokenizer(word, return_tensors="pt", truncation=True)
                with torch.no_grad():
                    output = bert_model(**inputs)
                subject_embeddings.append(output.last_hidden_state[:, 0, :])
            
            for word in environment_words:
                inputs = bert_tokenizer(word, return_tensors="pt", truncation=True)
                with torch.no_grad():
                    output = bert_model(**inputs)
                environment_embeddings.append(output.last_hidden_state[:, 0, :])
            
            for word in behavior_words:
                inputs = bert_tokenizer(word, return_tensors="pt", truncation=True)
                with torch.no_grad():
                    output = bert_model(**inputs)
                behavior_embeddings.append(output.last_hidden_state[:, 0, :])
            
            # 计算平均原型嵌入
            subject_prototype = torch.mean(torch.cat(subject_embeddings, dim=0), dim=0)
            environment_prototype = torch.mean(torch.cat(environment_embeddings, dim=0), dim=0)
            behavior_prototype = torch.mean(torch.cat(behavior_embeddings, dim=0), dim=0)
            
            # 从文本中提取候选词
            words = jieba.cut(text)
            words = [w for w in words if w not in self.stopwords and len(w) > 1]
            
            # 计算每个词与类别原型的相似度
            for word in set(words):
                inputs = bert_tokenizer(word, return_tensors="pt", truncation=True)
                with torch.no_grad():
                    output = bert_model(**inputs)
                word_embedding = output.last_hidden_state[:, 0, :]
                
                # 计算与类别原型的余弦相似度
                subject_sim = F.cosine_similarity(word_embedding, subject_prototype.unsqueeze(0))
                environment_sim = F.cosine_similarity(word_embedding, environment_prototype.unsqueeze(0))
                behavior_sim = F.cosine_similarity(word_embedding, behavior_prototype.unsqueeze(0))
                
                # 根据相似度分类
                sims = [
                    ("subject", subject_sim.item()),
                    ("environment", environment_sim.item()),
                    ("behavior", behavior_sim.item())
                ]
                
                # 找出最相似的类别
                best_category, best_sim = max(sims, key=lambda x: x[1])
                
                # 添加到相应类别
                result[best_category].append((word, best_sim))
            
            # 对每个类别的结果按相似度排序
            for category in result:
                result[category] = sorted(result[category], key=lambda x: x[1], reverse=True)
            
            return result
        
        except Exception as e:
            current_app.logger.error(f"使用模型提取语义标签时出错: {str(e)}")
            import traceback
            current_app.logger.error(traceback.format_exc())
            # 出错时返回空结果
            return {
                "subject": [],
                "environment": [],
                "behavior": []
            }
    
    def _split_sentences(self, text):
        """分割文本为句子"""
        if not text:
            return []
            
        # 常见的句子分隔符
        separators = ['。', '！', '？', '；', '……', '\n']
        sentences = []
        current_sentence = ""
        
        for char in text:
            current_sentence += char
            if char in separators:
                sentences.append(current_sentence.strip())
                current_sentence = ""
        
        # 处理最后一个句子
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
            
        return sentences
    
    def _extract_pos_words(self, text):
        """根据词性提取词汇"""
        if not text:
            return {"subject": [], "environment": [], "behavior": []}
            
        result = {
            "subject": [],
            "environment": [],
            "behavior": []
        }
        
        words = pseg.cut(text)
        
        for word, pos in words:
            if len(word) <= 1 and pos not in ["nr", "ns", "nt"]:
                continue
                
            if word in self.stopwords:
                continue
                
            if pos in self.semantic_categories["subject"]:
                result["subject"].append((word, 1))
            elif pos in self.semantic_categories["environment"]:
                result["environment"].append((word, 1))
            elif pos in self.semantic_categories["behavior"]:
                result["behavior"].append((word, 1))
        
        return result
    
    def _analyze_sentence_semantics(self, sentence):
        """分析句子的语义结构，提取主体、环境、行为"""
        try:
            if not sentence.strip():
                return {"subject": [], "environment": [], "behavior": []}
                
            # 提取句子中的词性
            words_with_pos = list(pseg.cut(sentence))
            words_dict = {}
            for pair in words_with_pos:
                if pair.word not in self.stopwords:
                    words_dict[pair.word] = pair.flag
            
            # 根据句子结构提取语义
            semantics = {
                "subject": [],    # 主体语义
                "environment": [], # 环境语义
                "behavior": []      # 行为语义
            }
            
            # 首先检查特殊词汇
            for pair in words_with_pos:
                word = pair.word
                pos = pair.flag
                if word in self.special_words and word not in self.stopwords:
                    category = self.special_words[word]
                    # 给特殊词汇更高的权重
                    semantics[category].append((word, 3))
            
            # 根据词性分类
            for pair in words_with_pos:
                word = pair.word
                pos = pair.flag
                if word in self.stopwords or len(word) <= 1 and pos not in ["nr", "ns", "nt"]:
                    continue
                    
                # 检查是否已经分类
                already_classified = False
                for category in ["subject", "environment", "behavior"]:
                    if any(w == word for w, _ in semantics[category]):
                        already_classified = True
                        break
                        
                if already_classified:
                    continue
                    
                # 根据词性分类
                if pos in self.semantic_categories["subject"]:
                    semantics["subject"].append((word, 1))
                elif pos in self.semantic_categories["environment"]:
                    semantics["environment"].append((word, 1))
                elif pos in self.semantic_categories["behavior"]:
                    semantics["behavior"].append((word, 1))
            
            return semantics
        except Exception as e:
            current_app.logger.error(f"分析句子语义时出错: {e}")
            return {"subject": [], "environment": [], "behavior": []}

def load_semantic_model():
    """
    加载语义模型
    """
    global bert_model, bert_tokenizer
    
    try:
        if bert_model is not None and bert_tokenizer is not None:
            current_app.logger.info("语义模型已加载，跳过")
            return True
            
        # 检查是否配置使用AI模型
        if not current_app.config.get('USE_AI_MODEL', False):
            current_app.logger.warning("未启用AI模型，跳过加载语义模型")
            return False
            
        # 检查transformers库版本
        try:
            import transformers
            current_app.logger.info(f"当前transformers库版本: {transformers.__version__}")
        except ImportError:
            current_app.logger.error("未安装transformers库")
            return False
            
        # 尝试导入必要的类
        try:
            from transformers import BertModel, BertTokenizer
        except ImportError as e:
            current_app.logger.error(f"导入BERT相关类失败: {str(e)}")
            return False
        
        # 获取模型路径
        model_path = current_app.config.get('SEMANTIC_MODEL_PATH')
        if not model_path:
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'chinese-bert-wwm-ext')
            
        # 检查模型路径是否存在
        if not os.path.exists(model_path):
            current_app.logger.warning(f"语义模型路径不存在: {model_path}")
            return False
            
        # 检查模型文件是否存在
        model_files = ['config.json', 'vocab.txt', 'pytorch_model.bin']
        missing_files = [f for f in model_files if not os.path.exists(os.path.join(model_path, f))]
        
        if missing_files:
            current_app.logger.warning(f"模型文件不完整，缺少: {', '.join(missing_files)}")
            return False
            
        current_app.logger.info(f"加载语义模型: {model_path}")
        
        # 加载模型和分词器
        try:
            bert_tokenizer = BertTokenizer.from_pretrained(model_path)
            bert_model = BertModel.from_pretrained(model_path)
            bert_model.eval()  # 设置为评估模式
            
            current_app.logger.info("语义模型加载完成")
            return True
        except Exception as e:
            current_app.logger.error(f"加载BERT模型和分词器失败: {str(e)}")
            return False
        
    except Exception as e:
        current_app.logger.error(f"加载语义模型失败: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return False

def extract_labels_from_text(text, num_per_category=3):
    """
    从文本中提取语义标签的入口函数
    """
    try:
        # 尝试加载模型
        load_semantic_model()
        
        # 创建语义提取器
        labeler = ChineseSemanticLabeler()
        
        # 提取标签
        labels = labeler.extract_labels(text, num_per_category)
        
        return labels
    except Exception as e:
        current_app.logger.error(f"提取语义标签时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        # 失败时返回空结果
        return {
            "subject": [],
            "environment": [],
            "behavior": []
        } 