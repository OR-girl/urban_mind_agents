"""
NLP Analyzer - NLP通道分析器

轻量级分析器，使用SnowNLP、jieba等工具进行低成本分析
"""

from collections import Counter
from typing import Any

import jieba
from snownlp import SnowNLP


class NLPAnalyzer:
    """
    NLP通道分析器
    
    用于长尾POI的低成本分析
    """

    POSITIVE_KEYWORDS = [
        "好吃", "美味", "推荐", "不错", "满意",
        "惊艳", "值得", "环境好", "服务好", "新鲜",
    ]
    NEGATIVE_KEYWORDS = [
        "难吃", "贵", "排队", "慢", "差",
        "失望", "不推荐", "坑", "脏", "服务差",
    ]
    QUEUE_KEYWORDS = ["排队", "等位", "等了", "人多", "拥挤"]

    def analyze(
        self,
        poi: dict[str, Any],
        reviews: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        分析POI评论
        
        Args:
            poi: POI字典
            reviews: 评论列表
            
        Returns:
            分析结果字典
        """
        if not reviews:
            return self._empty_result()

        # 情感分析
        sentiments = []
        for r in reviews:
            content = r.get("content", "")
            if content:
                try:
                    sentiment = SnowNLP(content).sentiments
                    sentiments.append(sentiment)
                except Exception:
                    sentiments.append(0.5)

        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.5

        # 关键词提取
        all_text = " ".join([r.get("content", "") for r in reviews])
        words = jieba.cut(all_text)
        word_freq = Counter(w for w in words if len(w) >= 2)

        # 亮点（高频正面词）
        highlights = [
            w for w, _ in word_freq.most_common(20)
            if any(kw in w for kw in self.POSITIVE_KEYWORDS)
        ][:3]

        # 避雷（高频负面词）
        warnings = [
            w for w, _ in word_freq.most_common(20)
            if any(kw in w for kw in self.NEGATIVE_KEYWORDS)
        ][:3]

        # 排队预警
        queue_mentions = sum(
            1 for r in reviews
            if any(kw in r.get("content", "") for kw in self.QUEUE_KEYWORDS)
        )
        queue_warning = ""
        if queue_mentions > 3:
            queue_ratio = queue_mentions / len(reviews) * 100
            queue_warning = f"约 {queue_ratio:.0f}% 评论提到排队"

        return {
            "highlights": highlights,
            "warnings": warnings,
            "best_time": "",
            "ugc_sentiment": {
                "food": min(5.0, avg_sentiment * 5),
                "service": min(5.0, avg_sentiment * 5),
                "environment": min(5.0, avg_sentiment * 5),
                "wait_time": max(0.0, 5.0 - (queue_mentions / len(reviews) * 5)) if reviews else 3.0,
            },
            "scene_tags": [],
            "queue_warning": queue_warning,
            "analysis_channel": "nlp",
            "confidence": 0.6,
        }

    def _empty_result(self) -> dict[str, Any]:
        """
        空结果
        """
        return {
            "highlights": [],
            "warnings": [],
            "best_time": "",
            "ugc_sentiment": {
                "food": 0.0,
                "service": 0.0,
                "environment": 0.0,
                "wait_time": 0.0,
            },
            "scene_tags": [],
            "queue_warning": "",
            "confidence": 0.0,
        }
