import os
import sys
from typing import Callable
from loguru import logger
from .handler import TraceHandler, TraceEvent
from nfctester.parsers import PN532HSUParser

# 6 层定义：name -> (loguru_level_no, default_enabled)
LAYER_DEFS = {
    "driver":   (5,   False),
    "debug":    (10,  False),
    "protocol": (15,  True),
    "warning":  (30,  True),
    "error":    (40,  True),
    "app":      (50,  True),
}


class FilterProxy:
    """过滤器代理：trace.filter.driver / trace.filter.level 控制层开关和级别"""
    __slots__ = ("_manager",)

    def __init__(self, manager):
        object.__setattr__(self, "_manager", manager)

    def __setattr__(self, name, value):
        if name in LAYER_DEFS:
            self._manager._layer_on[name] = bool(value)
            return
        if name == "level":
            self._manager._set_level(value)
            return
        raise AttributeError(f"'FilterProxy' has no attribute '{name}'")

    def __getattr__(self, name):
        if name in LAYER_DEFS:
            return self._manager._layer_on.get(name, False)
        if name == "level":
            return self._manager._min_level_name.lower()
        raise AttributeError(f"'FilterProxy' has no attribute '{name}'")


def trace_format(record):
    """动态格式化：用 layer 上下文替代 level 位置"""
    tag = record["extra"].get("layer", record["level"].name)
    msg = record["message"].replace("\n", "\n" + " " * 26)
    msg = msg.replace("{", "{{").replace("}", "}}")
    return f"<green>{{time:HH:mm:ss.SSS}}</green> | <level>{tag: <8}</level> | <level>{msg}</level>\n"


class TraceManager:
    """中心日志调度器，支持 6 层 (driver/debug/protocol/warning/error/app) 独立开关和 level 过滤"""

    def __init__(self):
        # 1. 注册自定义 loguru level
        try:
            logger.level("PROTOCOL")
        except ValueError:
            logger.level("PROTOCOL", no=15)

        # 2. 核心层级注册
        self._layers: dict[str, TraceHandler] = {}
        self._layer_on: dict[str, bool] = {}

        # 创建流式层 (driver, protocol) — 需要 TraceHandler 管理 buffer
        self._layers["driver"] = TraceHandler(
            layer_name="driver",
            logger_func=logger.bind(layer="driver").trace,
            parsers=[PN532HSUParser()],
        )
        self._layers["protocol"] = TraceHandler(
            layer_name="protocol",
            logger_func=logger.bind(layer="protocol").trace,
            parsers=[],
        )

        # 3. 文本层 (debug, warning, error, app) — 用 loguru 直接输出
        self._text_loggers = {
            "debug":   logger.bind(layer="debug").debug,
            "warning": logger.bind(layer="warning").warning,
            "error":   logger.bind(layer="error").error,
            "app":     logger.bind(layer="app").success,
        }

        # 4. 默认开关
        for name, (_, default) in LAYER_DEFS.items():
            self._layer_on[name] = default

        # 5. 从环境变量覆盖
        env_on = os.getenv("NFC_TRACE_LAYER", "")
        if env_on:
            for name in env_on.split(","):
                name = name.strip().lower()
                if name == "all":
                    for k in self._layer_on:
                        self._layer_on[k] = True
                elif name in self._layer_on:
                    self._layer_on[name] = True

        # 6. 最低 level 过滤
        self._min_level_name = os.getenv("NFC_TRACE_LEVEL", "warning").upper()
        self._reconfigure()

    # --- filter 代理 ---

    @property
    def filter(self) -> FilterProxy:
        return FilterProxy(self)

    def _set_level(self, value):
        if isinstance(value, int):
            self._min_level_name = self._level_no_to_name(value).upper()
        else:
            self._min_level_name = str(value).upper()
        self._reconfigure()

    def _level_no_to_name(self, no: int) -> str:
        """将数字 level 转换为 level 名"""
        mapping = {
            5: "DRIVER", 10: "DEBUG", 15: "PROTOCOL",
            30: "WARNING", 40: "ERROR", 50: "APP",
        }
        return mapping.get(no, "WARNING")

    # --- 核心过滤 ---

    def _filter(self, record):
        """核心过滤逻辑：层必须 ON 且层的 level >= min_level"""
        layer_name = record["extra"].get("layer")
        if layer_name is None:
            # 无层标签 → 走 loguru level 过滤
            return record["level"].no >= self._get_min_level_no()

        # 有层标签 → 层必须 ON 且层 level >= min_level
        if layer_name in LAYER_DEFS:
            layer_no = LAYER_DEFS[layer_name][0]
            return self._layer_on.get(layer_name, False) and layer_no >= self._get_min_level_no()

        return record["level"].no >= self._get_min_level_no()

    def _get_min_level_no(self) -> int:
        mapping = {
            "DRIVER": 5, "DEBUG": 10, "PROTOCOL": 15,
            "WARNING": 30, "ERROR": 40, "APP": 50,
        }
        return mapping.get(self._min_level_name, 30)

    def _reconfigure(self):
        """应用当前配置到全局 logger"""
        logger.remove()
        # 必须设为 TRACE 级别，过滤器才能接收到底层 Layer 的日志
        logger.add(sys.stdout, format=trace_format, filter=self._filter, level="TRACE")

    # --- 文本日志方法 ---

    def log(self, msg: str, layer: str = "app"):
        """通用文本日志，指定层"""
        layer = layer.lower()
        if layer in self._text_loggers:
            self._text_loggers[layer](msg)
        else:
            logger.info(msg)

    def app(self, msg):
        """输出到 app 层 (level=50)"""
        self.log(msg, layer="app")

    def debug(self, msg):
        """输出到 debug 层 (level=10)"""
        self.log(msg, layer="debug")

    def warning(self, msg):
        """输出到 warning 层 (level=30)"""
        self.log(msg, layer="warning")

    def error(self, msg):
        """输出到 error 层 (level=40)"""
        self.log(msg, layer="error")

    # --- 流式层输出方法 ---

    def driver(self, **kwargs):
        """输出到 driver 层 (level=5)"""
        handler = self._layers.get("driver")
        if handler:
            handler(**kwargs)

    def protocol(self, **kwargs):
        """输出到 protocol 层 (level=15)"""
        handler = self._layers.get("protocol")
        if handler:
            handler(**kwargs)

    # --- 层控制方法 ---

    def set_parse(self, level=1):
        """设置解析级别: 0=关闭(hex), 1=简单(hex + 摘要标签)"""
        for handler in self._layers.values():
            handler.parse_level = level

    def set_parser(self, atqa: int, sak: int):
        """根据 ATQA/SAK 从 ParserRegistry 动态设置协议解析器"""
        from nfctester.parsers.registry import ParserRegistry
        parser_cls = ParserRegistry.get(atqa, sak)
        if parser_cls:
            self._layers["protocol"].parsers = [parser_cls()]

    # --- Sink 管理 ---

    def add_sink(self, fn: Callable[[TraceEvent], None]):
        """注册结构化 trace 事件回调"""
        for handler in self._layers.values():
            handler.add_sink(fn)

    def remove_sink(self, fn: Callable[[TraceEvent], None]):
        """移除结构化 trace 事件回调"""
        for handler in self._layers.values():
            handler.remove_sink(fn)


trace = TraceManager()
