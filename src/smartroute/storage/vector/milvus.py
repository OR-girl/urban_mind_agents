"""
Milvus Client - Milvus向量数据库客户端

提供向量检索和存储功能
"""

from typing import Any

from pymilvus import MilvusClient as PyMilvusClient


class MilvusClient:
    """
    Milvus向量数据库客户端
    """

    def __init__(
        self,
        uri: str = "http://localhost:19530",
        collection_name: str = "poi_embeddings",
    ) -> None:
        self.uri = uri
        self.collection_name = collection_name
        self._client = None

    async def connect(self) -> None:
        """
        连接数据库
        """
        if self._client is None:
            self._client = PyMilvusClient(uri=self.uri)

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 10,
        filter_expr: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        向量检索
        
        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            top_k: 返回数量
            filter_expr: 过滤表达式
            output_fields: 输出字段
            
        Returns:
            检索结果列表
        """
        await self.connect()

        if output_fields is None:
            output_fields = ["poi_id", "name", "category", "location", "rating"]

        results = self._client.search(
            collection_name=collection_name,
            data=[query_vector],
            limit=top_k,
            filter=filter_expr or "",
            output_fields=output_fields,
        )

        # 解析结果
        parsed_results = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                parsed_results.append({
                    "poi_id": entity.get("poi_id", ""),
                    "name": entity.get("name", ""),
                    "category": entity.get("category", ""),
                    "location": entity.get("location", {}),
                    "rating": entity.get("rating", 0),
                    "distance": hit.get("distance", 0),
                })

        return parsed_results

    async def insert(
        self,
        collection_name: str,
        data: list[dict[str, Any]],
    ) -> None:
        """
        插入向量
        
        Args:
            collection_name: 集合名称
            data: 数据列表
        """
        await self.connect()
        self._client.insert(
            collection_name=collection_name,
            data=data,
        )

    async def create_collection(
        self,
        collection_name: str,
        dimension: int = 1024,
    ) -> None:
        """
        创建集合
        
        Args:
            collection_name: 集合名称
            dimension: 向量维度
        """
        await self.connect()

        if not self._client.has_collection(collection_name):
            self._client.create_collection(
                collection_name=collection_name,
                dimension=dimension,
            )

    async def delete(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        """
        删除向量
        
        Args:
            collection_name: 集合名称
            ids: ID列表
        """
        await self.connect()
        self._client.delete(
            collection_name=collection_name,
            ids=ids,
        )

    async def close(self) -> None:
        """
        关闭连接
        """
        if self._client:
            self._client.close()
            self._client = None
