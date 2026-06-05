from typing import Callable
from nfctester.parsers import BaseParser
from .formatter import TraceFormatter


class TraceHandler:
    """缓存与输出控制器，持有一组按优先级排列的解析器链"""

    def __init__(
        self,
        layer_name: str,
        logger_func: Callable[[str], None],
        parsers: list[BaseParser] = None,   # 按优先级排列，首个 can_parse 命中的生效
        enabled: bool = False,
    ):
        self.layer_name  = layer_name
        self.logger_func = logger_func
        self.parsers     = parsers or []
        self.enabled     = enabled
        self._tx_buffer  = bytearray()
        self._rx_buffer  = bytearray()

    def __call__(self, tx: bytes = None, rx: bytes = None, flush: bool = True):
        """处理日志输出，支持流式追加（flush=False）和立即输出（flush=True）"""
        if tx:
            raw = bytes(self._tx_buffer) + tx if self._tx_buffer else tx
            self._tx_buffer.clear()
            if flush:   self._emit("TX", raw)
            else:       self._tx_buffer.extend(raw)

        if rx:
            raw = bytes(self._rx_buffer) + rx if self._rx_buffer else rx
            self._rx_buffer.clear()
            if flush:   self._emit("RX", raw)
            else:       self._rx_buffer.extend(raw)

    def _emit(self, direction: str, raw: bytes):
        """依次尝试解析器链，命中则格式化输出，否则降级为原始 hex"""
        parser = next((p for p in self.parsers if p.can_parse(raw)), None)
        if parser:
            msg = TraceFormatter.format(direction, parser.parse(raw))
        else:
            msg = TraceFormatter.format_raw(direction, raw)
        self.logger_func(msg)
