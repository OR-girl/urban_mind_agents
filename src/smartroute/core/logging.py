"""
SmartRoute Agent 日志配置模块

使用 structlog 进行结构化日志记录
"""

import logging
import sys
from typing import Any

import structlog
from structlog.processors import CallsiteParameter


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    include_callsite: bool = True,
) -> None:
    """
    配置结构化日志

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: 输出格式 (json, console)
        include_callsite: 是否包含调用位置信息
    """
    # 设置标准库日志级别
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        stream=sys.stdout,
    )

    # 定义 structlog 处理器
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if include_callsite:
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                ],
            )
        )

    # 根据格式选择渲染器
    if format_type == "console":
        # 开发环境使用彩色输出
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # 生产环境使用 JSON 格式
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 添加最终渲染处理器
    logging.root.handlers[0].formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[renderer],
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    获取日志器实例

    Args:
        name: 日志器名称，默认为调用模块名

    Returns:
        BoundLogger 实例
    """
    return structlog.get_logger(name)


class AgentLogger:
    """
    Agent 专用日志器

    自动注入 trace_id、agent_name 等上下文信息
    """

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self._logger = get_logger(f"agent.{agent_name}")

    def bind_context(self, trace_id: str, session_id: str, **kwargs: Any) -> None:
        """绑定上下文信息"""
        self._logger = self._logger.bind(
            trace_id=trace_id,
            session_id=session_id,
            agent=self.agent_name,
            **kwargs,
        )

    def info(self, message: str, **kwargs: Any) -> None:
        """记录 INFO 级别日志"""
        self._logger.info(message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """记录 DEBUG 级别日志"""
        self._logger.debug(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """记录 WARNING 级别日志"""
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """记录 ERROR 级别日志"""
        self._logger.error(message, **kwargs)

    def timing(self, operation: str, duration_ms: float, **kwargs: Any) -> None:
        """记录耗时信息"""
        self._logger.info(
            f"{operation} completed",
            operation=operation,
            duration_ms=duration_ms,
            **kwargs,
        )

    def llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
        cost_yuan: float,
    ) -> None:
        """记录 LLM 调用信息"""
        self._logger.info(
            "llm_call",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            cost_yuan=cost_yuan,
        )


# 初始化默认日志配置
setup_logging()