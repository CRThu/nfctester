from .base_parser import BaseParser, ParsedField, ParsedFrame

# ── 字段规格: (name, byte_length, desc_fn(raw_bytes) -> str) ─────────────────
# None 长度表示"剩余所有字节"
_FS = lambda n, l, f: (n, l, f)   # noqa: E731 — 仅用于缩短下方表格行宽

def _blk(b):  return f"Block {b[0]} / Sector {b[0] // 4}"
def _key(b):  return "6-byte auth key"
def _uid(b):  return f"Card UID"
def _crc(b):  return "ISO14443A CRC-A"
def _rsv(b):  return "Must be 0x00"
def _pay(b):  return f"{len(b)} bytes"

# 指令表: cmd_byte -> (label, [ field_specs... ])
# field_spec: (name, length, desc_fn)   length=None → 剩余字节
_CMD_TABLE: dict[int, tuple[str, list]] = {
    0x30: ("READ",      [_FS("Block Number", 1, _blk), _FS("CRC", 2, _crc)]),
    0xA0: ("WRITE",     [_FS("Block Number", 1, _blk), _FS("Data", 16, _pay)]),
    0xA2: ("WRITE",     [_FS("Block Number", 1, _blk), _FS("Data",  4, _pay)]),
    0x50: ("HALT",      [_FS("Reserved",     1, _rsv), _FS("CRC",   2, _crc)]),
    0x60: ("AUTH_A",    [_FS("Block Number", 1, _blk), _FS("Key A", 6, _key), _FS("UID", 4, _uid)]),
    0x61: ("AUTH_B",    [_FS("Block Number", 1, _blk), _FS("Key B", 6, _key), _FS("UID", 4, _uid)]),
    0xC0: ("DECREMENT", [_FS("Block Number", 1, _blk), _FS("Value", 4, _pay)]),
    0xC1: ("INCREMENT", [_FS("Block Number", 1, _blk), _FS("Value", 4, _pay)]),
    0xC2: ("RESTORE",   [_FS("Block Number", 1, _blk)]),
    0xB0: ("TRANSFER",  [_FS("Block Number", 1, _blk)]),
}


def _parse_fields(data: bytes, offset: int, specs: list) -> list[ParsedField]:
    """按 field_spec 列表顺序切分 data，生成 ParsedField 列表"""
    result = []
    for name, length, desc_fn in specs:
        chunk = data[offset:] if length is None else data[offset:offset + length]
        if not chunk:
            break
        result.append(ParsedField(name, chunk, int.from_bytes(chunk, "big"), desc_fn(chunk)))
        offset += len(chunk)
    return result


class MifareClassicParser(BaseParser):
    """Mifare Classic 指令层解析器（InDataExchange 剥离 PN532 封装后的原始数据）"""

    def can_parse(self, data: bytes) -> bool:
        return len(data) >= 1 and data[0] in _CMD_TABLE

    def parse(self, data: bytes) -> ParsedFrame:
        cmd = data[0]
        label, specs = _CMD_TABLE.get(cmd, (f"UNKNOWN (0x{cmd:02X})", []))
        fields = [ParsedField("Command", data[0:1], cmd, label)]
        fields += _parse_fields(data, 1, specs)
        return ParsedFrame(raw=data, label=f"Mifare Classic — {label}", fields=fields)
