import os
import sys
from typing import Callable
from loguru import logger
from .handler import TraceHandler, TraceEvent
from nfctester.parsers import PN532HSUParser, MifareClassicParser, T2TParser


def trace_format(record):
    """动态格式化：用 layer 上下文替代 level 位置"""
    tag = record["extra"].get("layer", record["level"].name)
    msg = record["message"].replace("\n", "\n" + " " * 26)
    msg = msg.replace("{", "{{").replace("}", "}}")
    return f"<green>{{time:HH:mm:ss.SSS}}</green> | <level>{tag: <8}</level> | <level>{msg}</level>\n"



class TraceManager:
    """中心日志调度器，支持动态切换层级(Layer)和级别(Level)"""

    def __init__(self):
        # 1. 核心层级注册 (默认关闭)
        parse_level = self._get_parse_level()
        self._layers: dict[str, TraceHandler] = {
            "DRIVER": TraceHandler(
                layer_name="DRIVER",
                logger_func=logger.bind(layer="DRIVER").trace,
                parsers=[PN532HSUParser()],
                parse_level=parse_level,
            ),
            "PROTOCOL": TraceHandler(
                layer_name="PROTOCOL",
                logger_func=logger.bind(layer="PROTOCOL").trace,
                parsers=[MifareClassicParser(), T2TParser()],
                parse_level=parse_level,
            ),
        }

        # 2. 快捷访问属性 (兼容旧代码)
        self.driver = self._layers["DRIVER"]
        self.protocol = self._layers["PROTOCOL"]

        # 3. 全局级别配置
        self._min_level = os.getenv("CRFT_TRACE_LEVEL", "INFO").upper()

        # 4. 从环境变量注入初始 Layer 开关
        self.driver.enabled = self._get_env_bool("CRFT_TRACE_DRIVER", False)
        self.protocol.enabled = self._get_env_bool("CRFT_TRACE_PROTOCOL", False)

        self._reconfigure()

    def _get_env_bool(self, key, default):
        val = os.getenv(key, str(default)).lower()
        return val in ("1", "true", "yes", "on")

    def _get_parse_level(self):
        val = os.getenv("CRFT_TRACE_PARSE", "1").lower()
        if val in ("0", "false", "no", "off"):
            return 0
        return 1

    def _filter(self, record):
        """核心过滤逻辑：Layer 开关优先，普通日志走 Level 过滤"""
        layer_name = record["extra"].get("layer")
        
        # 如果是已知层级，由该层级的 Handler.enabled 决定
        if layer_name in self._layers:
            return self._layers[layer_name].enabled
        
        # 否则按全局级别过滤
        try:
            return record["level"].no >= logger.level(self._min_level).no
        except ValueError:
            return record["level"].no >= 20 # 默认 INFO

    def _reconfigure(self):
        """应用当前配置到全局 logger"""
        logger.remove()
        # 必须设为 TRACE 级别，过滤器才能接收到底层 Layer 的日志
        logger.add(sys.stdout, format=trace_format, filter=self._filter, level="TRACE")

    def set_level(self, level):
        """设置通用日志输出级别 (INFO, DEBUG, ERROR等)"""
        self._min_level = level.upper()
        self._reconfigure()

    def set_layer(self, layer_name, enable=True):
        """开启或关闭特定层级的详细追踪 (DRIVER/PROTOCOL)"""
        name = layer_name.upper()
        if name in self._layers:
            self._layers[name].enabled = enable

    def set_parse(self, level=1):
        """设置解析级别: 0=关闭(hex), 1=简单(hex + 摘要标签)"""
        for handler in self._layers.values():
            handler.parse_level = level

    def set_card_type(self, card_type: str):
        """设置当前卡片类型，注入到所有协议解析器的 state 中"""
        for handler in self._layers.values():
            for parser in handler.parsers:
                parser.state["card_type"] = card_type

    def add_sink(self, fn: Callable[[TraceEvent], None]):
        """注册结构化 trace 事件回调"""
        for handler in self._layers.values():
            handler.add_sink(fn)

    def remove_sink(self, fn: Callable[[TraceEvent], None]):
        """移除结构化 trace 事件回调"""
        for handler in self._layers.values():
            handler.remove_sink(fn)

    def info(self, msg):    logger.info(msg)
    def error(self, msg):   logger.error(msg)
    def warning(self, msg): logger.warning(msg)
    def success(self, msg): logger.success(msg)
    def debug(self, msg):   logger.debug(msg)


trace = TraceManager()
