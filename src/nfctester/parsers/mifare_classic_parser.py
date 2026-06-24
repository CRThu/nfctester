from .table_parser import TableParser


def _blk(b): return f"Block {b[0]} / Sector {b[0] // 4}"
def _pay(b): return f"{len(b)} bytes"


class MifareClassicParser(TableParser):
    """Mifare Classic 指令层解析器

    CMD_TABLE 仅描述 trace 中实际存在的字节。
    Key/UID 由 PN532 硬件内部处理，不出现在 trace 中。
    """

    CMD_TABLE = {
        0x30: ("READ",      [("Block Number", 1, _blk)]),
        0xA0: ("WRITE",     [("Block Number", 1, _blk), ("Data", 16, _pay)]),
        0xA2: ("WRITE",     [("Block Number", 1, _blk), ("Data",  4, _pay)]),
        0x50: ("HALT",      []),
        0x60: ("AUTH_A",    [("Block Number", 1, _blk)]),
        0x61: ("AUTH_B",    [("Block Number", 1, _blk)]),
        0xC0: ("DECREMENT", [("Block Number", 1, _blk), ("Value", 4, _pay)]),
        0xC1: ("INCREMENT", [("Block Number", 1, _blk), ("Value", 4, _pay)]),
        0xC2: ("RESTORE",   [("Block Number", 1, _blk)]),
        0xB0: ("TRANSFER",  [("Block Number", 1, _blk)]),
    }
