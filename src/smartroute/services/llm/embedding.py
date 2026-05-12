"""
Embedding Service - 向量化服务

使用BGE-M3模型进行文本向量化
"""

from typing import Any

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """
    向量化服务
    
    使用BGE-M3模型
    """

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self.model_name = model_name
        self._model = None

    async def encode(self, text: str) -> list[float]:
        """
        编码文本
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表
        """
        model = await self._get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量编码
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        model = await self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]

    async def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def get_dimension(self) -> int:
        """
        获取向量维度
        """
        return 1024  # BGE-M3 默认维度
