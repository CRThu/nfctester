from .base_parser import BaseParser, ParsedField, ParsedFrame
from .mifare_classic_parser import _parse_fields

# ACK/NACK 单字节响应
_RESPONSES = {
    0x0A: "ACK — Success",
    0x05: "NACK — Invalid argument",
    0x00: "NACK — Not authenticated / Parity error",
}

def _page(b):  return f"Page {b[0]} (byte offset {b[0] * 4})"
def _data(b):  return f"{len(b)} bytes"
def _pwd(b):   return "4-byte password"
def _pack(b):  return "2-byte password ACK"

# 指令表: cmd_byte -> (label, [ field_specs... ])
_CMD_TABLE: dict[int, tuple[str, list]] = {
    0x30: ("READ",      [("Page Address", 1, _page)]),
    0xA2: ("WRITE",     [("Page Address", 1, _page), ("Write Data", 4, _data)]),
    0x50: ("HALT",      [("Reserved",     1, lambda _: "Must be 0x00")]),
    0x1B: ("PWD_AUTH",  [("Password",     4, _pwd)]),
    0x3C: ("READ_SIG",  [("Address",      1, lambda _: "Fixed 0x00")]),
    0x60: ("AUTH",      [("Address",      1, _page)]),
}


class T2TParser(BaseParser):
    """NFC Forum Type 2 Tag 指令层解析器"""

    def can_parse(self, data: bytes) -> bool:
        if not data:
            return False
        return (len(data) == 1 and data[0] in _RESPONSES) or data[0] in _CMD_TABLE

    def parse(self, data: bytes) -> ParsedFrame:
        # 单字节 ACK/NACK
        if len(data) == 1 and data[0] in _RESPONSES:
            return ParsedFrame(
                raw=data, label="T2T Response",
                fields=[ParsedField("Response", data, data[0], _RESPONSES[data[0]])]
            )

        cmd = data[0]
        label, specs = _CMD_TABLE.get(cmd, (f"UNKNOWN (0x{cmd:02X})", []))
        fields = [ParsedField("Command", data[0:1], cmd, label)]
        fields += _parse_fields(data, 1, specs)
        return ParsedFrame(raw=data, label=f"T2T — {label}", fields=fields)
