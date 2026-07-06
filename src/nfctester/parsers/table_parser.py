from .base_parser import BaseParser, ParsedField, ParsedFrame


class TableParser(BaseParser):
    """基于指令表的解析器基类。

    子类只需定义:
        CMD_TABLE: dict[int, tuple[str, list]]
            cmd_byte -> (label, [(name, length, desc_fn), ...])
            length=None 表示剩余所有字节
            specs 仅描述 trace 中实际存在的字节（不含硬件内部处理的部分）
        RESPONSES: dict[int, str] | None
            单字节响应码 -> 描述 (可选)

    summary() 自动生成: "LABEL Field0xHH" 或 "LABEL (N bytes)"
    子类可覆写 summary() 提供更精确的描述。
    """

    CMD_TABLE: dict[int, tuple[str, list]] = {}
    RESPONSES: dict[int, str] | None = None

    def can_parse(self, data: bytes) -> bool:
        if not data:
            return False
        return data[0] in self.CMD_TABLE

    def summary(self, data: bytes) -> str | None:
        cmd = data[0]
        if cmd not in self.CMD_TABLE:
            return None
        label, specs = self.CMD_TABLE[cmd]
        if not specs or len(data) < 2:
            return label
        _, length, _ = specs[0]
        if length == 1:
            return f"{label} 0x{data[1]:02X}"
        if length is not None:
            return f"{label} ({length} bytes)"
        return f"{label} ({len(data) - 1} bytes)"

    def parse_rx(self, data: bytes, tx: bytes = None) -> ParsedFrame | None:
        """根据 TX 上下文解析 RX 响应。仅匹配 RESPONSES 中的单字节响应码。"""
        if not data or not self.RESPONSES or len(data) != 1:
            return None
        code = data[0]
        if code not in self.RESPONSES:
            return None
        desc = self.RESPONSES[code]
        label = desc.split("—")[0].strip() if "—" in desc else "Response"
        return ParsedFrame(
            raw=data, label=label,
            fields=[ParsedField("Response", data, code, desc)]
        )

    def parse(self, data: bytes) -> ParsedFrame:
        cmd = data[0]
        label, specs = self.CMD_TABLE.get(cmd, (f"UNKNOWN (0x{cmd:02X})", []))
        fields = [ParsedField("Command", data[0:1], cmd, label)]
        fields += self._parse_fields(data, 1, specs)
        return ParsedFrame(raw=data, label=label, fields=fields)

    def _parse_fields(self, data: bytes, offset: int, specs: list) -> list[ParsedField]:
        """按 field_spec 列表顺序切分 data，生成 ParsedField 列表"""
        result = []
        for name, length, desc_fn in specs:
            chunk = data[offset:] if length is None else data[offset:offset + length]
            if not chunk:
                break
            result.append(ParsedField(name, chunk, int.from_bytes(chunk, "big"), desc_fn(chunk)))
            offset += len(chunk)
        return result
