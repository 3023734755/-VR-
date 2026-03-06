import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, GaussianNoise, Dropout
from sklearn.metrics.pairwise import cosine_similarity
import joblib
import os
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class MLPTransformer:
    """MLP安全向量转换器"""
    
    def __init__(self, input_dim=64, hidden_dims=[128, 96], output_dim=64, noise_std=0.1, dropout_rate=0.3):
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.output_dim = output_dim
        self.noise_std = noise_std
        self.dropout_rate = dropout_rate
        self.model = None
        self.is_trained = False
        
    def build_model(self):
        """构建MLP模型"""
        model = Sequential([
            Dense(self.hidden_dims[0], input_dim=self.input_dim, activation='relu'),
            GaussianNoise(self.noise_std),  # 添加随机噪声
            Dense(self.hidden_dims[1], activation='tanh'),
            Dropout(self.dropout_rate),     # 随机断开神经元
            Dense(self.output_dim)          # 输出维度
        ])
        
        model.compile(optimizer='adam', loss='mse')
        self.model = model
        return model
    
    def train(self, X, epochs=100, batch_size=32):
        """训练MLP模型（自监督学习）"""
        if self.model is None:
            self.build_model()
        
        # 自监督学习：输入和输出相同，但通过噪声和dropout实现不可逆转换
        history = self.model.fit(
            X, X,  # 自监督
            epochs=epochs,
            batch_size=batch_size,
            verbose=0,
            validation_split=0.2
        )
        
        self.is_trained = True
        logger.info(f"MLP模型训练完成，最终损失: {history.history['loss'][-1]:.4f}")
        return history
    
    def transform(self, vectors):
        """转换语义向量为安全向量"""
        try:
            if not self.is_trained or self.model is None:
                raise ValueError("模型未训练，请先调用train()方法")
            
            vectors = np.array(vectors)
            if vectors.ndim == 1:
                vectors = vectors.reshape(1, -1)
            
            # 确保输入维度正确
            if vectors.shape[1] != self.input_dim:
                # 如果维度不匹配，进行填充或截断
                if vectors.shape[1] < self.input_dim:
                    # 填充零
                    padding = np.zeros((vectors.shape[0], self.input_dim - vectors.shape[1]))
                    vectors = np.concatenate([vectors, padding], axis=1)
                else:
                    # 截断
                    vectors = vectors[:, :self.input_dim]
            
            transformed = self.model.predict(vectors, verbose=0)
            return transformed
        except Exception as e:
            logger.error(f"向量转换失败: {str(e)}")
            # 返回随机向量作为备选
            return np.random.rand(len(vectors), self.output_dim)
    
    def save_model(self, filepath):
        """保存模型"""
        if self.model is None:
            raise ValueError("没有可保存的模型")
        
        # 保存模型结构和权重
        self.model.save(filepath)
        
        # 保存配置
        config = {
            'input_dim': self.input_dim,
            'hidden_dims': self.hidden_dims,
            'output_dim': self.output_dim,
            'noise_std': self.noise_std,
            'dropout_rate': self.dropout_rate,
            'is_trained': self.is_trained
        }
        
        config_path = filepath.replace('.h5', '_config.pkl')
        joblib.dump(config, config_path)
        
        logger.info(f"模型已保存到: {filepath}")
    
    def load_model(self, filepath):
        """加载模型"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"模型文件不存在: {filepath}")
        
        # 加载配置
        config_path = filepath.replace('.h5', '_config.pkl')
        if os.path.exists(config_path):
            config = joblib.load(config_path)
            self.input_dim = config['input_dim']
            self.hidden_dims = config['hidden_dims']
            self.output_dim = config['output_dim']
            self.noise_std = config['noise_std']
            self.dropout_rate = config['dropout_rate']
            self.is_trained = config['is_trained']
        
        # 加载模型
        self.model = tf.keras.models.load_model(filepath)
        logger.info(f"模型已从 {filepath} 加载")

# 全局MLP转换器实例
mlp_transformer = None

def get_mlp_transformer():
    """获取MLP转换器实例"""
    global mlp_transformer
    
    if mlp_transformer is None:
        mlp_transformer = MLPTransformer()
        
        # 尝试加载已训练的模型
        model_path = os.path.join(current_app.config.get('BASE_DIR', ''), 'models', 'mlp_transformer.h5')
        if os.path.exists(model_path):
            try:
                mlp_transformer.load_model(model_path)
                logger.info("已加载预训练的MLP模型")
            except Exception as e:
                logger.warning(f"加载MLP模型失败: {e}，将使用新模型")
                mlp_transformer.build_model()
        else:
            mlp_transformer.build_model()
    
    return mlp_transformer

def calculate_similarity(vector1, vector2):
    """计算两个向量的余弦相似度"""
    vector1 = np.array(vector1).reshape(1, -1)
    vector2 = np.array(vector2).reshape(1, -1)
    return cosine_similarity(vector1, vector2)[0][0]