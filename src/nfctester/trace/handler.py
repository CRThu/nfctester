import time
from dataclasses import dataclass, field
from typing import Callable
from nfctester.parsers import BaseParser, ParsedFrame
from .formatter import TraceFormatter


@dataclass
class TraceEvent:
    """结构化 trace 事件，供外部 sink 消费"""
    layer: str
    direction: str
    raw: bytes
    parsed: ParsedFrame | None
    summary: str | None
    formatted: str
    timestamp: float


class TraceHandler:
    """缓存与输出控制器，持有一组按优先级排列的解析器链"""

    def __init__(
        self,
        layer_name: str,
        logger_func: Callable[[str], None],
        parsers: list[BaseParser] = None,
        enabled: bool = False,
        parse_level: int = 1,
    ):
        self.layer_name   = layer_name
        self.logger_func  = logger_func
        self.parsers      = parsers or []
        self.enabled      = enabled
        self.parse_level  = parse_level
        self._tx_buffer   = bytearray()
        self._rx_buffer   = bytearray()
        self._last_tx: bytes | None = None
        self._sinks: list[Callable[[TraceEvent], None]] = []

    def add_sink(self, fn: Callable[[TraceEvent], None]):
        if fn not in self._sinks:
            self._sinks.append(fn)

    def remove_sink(self, fn: Callable[[TraceEvent], None]):
        if fn in self._sinks:
            self._sinks.remove(fn)

    def __call__(self, tx: bytes = None, rx: bytes = None, flush: bool = True):
        """处理日志输出，支持流式追加（flush=False）和立即输出（flush=True）"""
        if tx:
            raw = bytes(self._tx_buffer) + tx if self._tx_buffer else tx
            self._tx_buffer.clear()
            self._last_tx = raw
            if flush:   self._emit("TX", raw)
            else:       self._tx_buffer.extend(raw)

        if rx:
            raw = bytes(self._rx_buffer) + rx if self._rx_buffer else rx
            self._rx_buffer.clear()
            if flush:   self._emit("RX", raw)
            else:       self._rx_buffer.extend(raw)

    def _emit(self, direction: str, raw: bytes):
        parsed = None
        summary = None

        if direction == "TX":
            msg, parsed, summary = self._emit_tx(raw)
        else:
            msg, parsed, summary = self._emit_rx(raw)

        self.logger_func(msg)
        self._notify_sinks(direction, raw, parsed, summary, msg)

    def _emit_tx(self, raw: bytes) -> tuple[str, ParsedFrame | None, str | None]:
        if self.parse_level == 0:
            return TraceFormatter.format_raw("TX", raw), None, None

        parser = next((p for p in self.parsers if p.can_parse(raw)), None)
        if not parser:
            return TraceFormatter.format_raw("TX", raw), None, None

        summary = parser.summary(raw)
        if summary:
            return TraceFormatter.format_summary("TX", raw, summary), None, summary
        return TraceFormatter.format_raw("TX", raw), None, None

    def _emit_rx(self, raw: bytes) -> tuple[str, ParsedFrame | None, str | None]:
        if self.parse_level == 0:
            return TraceFormatter.format_raw("RX", raw), None, None

        for parser in self.parsers:
            frame = parser.parse_rx(raw, tx=self._last_tx)
            if frame:
                summary = frame.label
                if self.parse_level == 1:
                    return TraceFormatter.format_summary("RX", raw, summary), frame, summary
                return TraceFormatter.format_raw("RX", raw), frame, None

        return TraceFormatter.format_raw("RX", raw), None, None

    def _notify_sinks(self, direction, raw, parsed, summary, msg):
        if not self._sinks:
            return
        event = TraceEvent(
            layer=self.layer_name,
            direction=direction,
            raw=raw,
            parsed=parsed,
            summary=summary,
            formatted=msg,
            timestamp=time.time(),
        )
        for fn in self._sinks:
            try:
                fn(event)
            except Exception:
                pass
