"""
SmartRoute Agent 日志配置模块

使用 structlog 进行结构化日志记录（可选，自动降级到标准 logging）
"""
import logging as _logging
import sys
from typing import Any

try:
    import structlog as _structlog
    from structlog.processors import CallsiteParameter
    _HAS_STRUCTLOG = True
except ImportError:
    _structlog = None  # type: ignore
    CallsiteParameter = None  # type: ignore
    _HAS_STRUCTLOG = False


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    include_callsite: bool = True,
) -> None:
    if not _HAS_STRUCTLOG:
        _logging.basicConfig(level=getattr(_logging, level.upper()), stream=sys.stdout)
        return

    _logging.basicConfig(level=getattr(_logging, level.upper()), stream=sys.stdout)
    shared_processors: list[Any] = [
        _structlog.contextvars.merge_contextvars,
        _structlog.stdlib.add_log_level,
        _structlog.stdlib.add_logger_name,
        _structlog.processors.TimeStamper(fmt="iso"),
        _structlog.processors.StackInfoRenderer(),
    ]
    if include_callsite:
        shared_processors.append(
            _structlog.processors.CallsiteParameterAdder(
                parameters=[CallsiteParameter.FILENAME, CallsiteParameter.FUNC_NAME, CallsiteParameter.LINENO],
            )
        )
    renderer = _structlog.dev.ConsoleRenderer(colors=True) if format_type == "console" else _structlog.processors.JSONRenderer()
    _structlog.configure(
        processors=[*shared_processors, _structlog.stdlib.PositionalArgumentsFormatter(), _structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=_structlog.stdlib.LoggerFactory(),
        wrapper_class=_structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    _logging.root.handlers[0].formatter = _structlog.stdlib.ProcessorFormatter(foreign_pre_chain=shared_processors, processors=[renderer])


def get_logger(name: str | None = None):
    """获取日志器（structlog 可用时返回 BoundLogger，否则返回标准 Logger）"""
    if _HAS_STRUCTLOG:
        return _structlog.get_logger(name)
    return _logging.getLogger(name)


class AgentLogger:
    """Agent 专用日志器，自动注入 trace_id、agent_name 等上下文"""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self._logger = get_logger(f"agent.{agent_name}")

    def bind_context(self, trace_id: str, session_id: str, **kwargs: Any) -> None:
        if _HAS_STRUCTLOG:
            self._logger = self._logger.bind(trace_id=trace_id, session_id=session_id, agent=self.agent_name, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        if _HAS_STRUCTLOG: self._logger.info(message, **kwargs)
        else: self._logger.info("%s %s", message, kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        if _HAS_STRUCTLOG: self._logger.debug(message, **kwargs)
        else: self._logger.debug("%s %s", message, kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        if _HAS_STRUCTLOG: self._logger.warning(message, **kwargs)
        else: self._logger.warning("%s %s", message, kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        if _HAS_STRUCTLOG: self._logger.error(message, **kwargs)
        else: self._logger.error("%s %s", message, kwargs)

    def timing(self, operation: str, duration_ms: float, **kwargs: Any) -> None:
        if _HAS_STRUCTLOG: self._logger.info(f"{operation} completed", operation=operation, duration_ms=duration_ms, **kwargs)
        else: self._logger.info("%s completed in %.1fms %s", operation, duration_ms, kwargs)

    def llm_call(self, model: str, input_tokens: int, output_tokens: int, duration_ms: float, cost_yuan: float) -> None:
        if _HAS_STRUCTLOG: self._logger.info("llm_call", model=model, input_tokens=input_tokens, output_tokens=output_tokens, duration_ms=duration_ms, cost_yuan=cost_yuan)
        else: self._logger.info("llm_call model=%s in=%d out=%d %.1fms ¥%.4f", model, input_tokens, output_tokens, duration_ms, cost_yuan)


setup_logging()
