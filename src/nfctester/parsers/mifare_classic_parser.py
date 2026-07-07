from .table_parser import TableParser
from .base_parser import ParsedField, ParsedFrame
from .registry import ParserRegistry


def _blk(b): return f"Block {b[0]} / Sector {b[0] // 4}"
def _pay(b): return f"{len(b)} bytes"


@ParserRegistry.register(atqa=0x0004, sak=0x08, name="MIFARE Classic 1K")
@ParserRegistry.register(atqa=0x0044, sak=0x08, name="MIFARE Classic 1K (7-byte UID)")
@ParserRegistry.register(atqa=0x0002, sak=0x18, name="MIFARE Classic 4K")
@ParserRegistry.register(atqa=0x0004, sak=0x18, name="MIFARE Classic 4K (alt)")
class MifareClassicParser(TableParser):
    """Mifare Classic 指令层解析器

    CMD_TABLE 仅描述 trace 中实际存在的字节。
    Key/UID 由 PN532 硬件内部处理，不出现在 trace 中。
    """

    RESPONSES = {
        0x00: "ACK — Operation successful",
        0x01: "NACK — Not acknowledged",
    }

    CMD_TABLE = {
        0x30: ("READ",      [("Block Number", 1, _blk)]),
        0xA0: ("WRITE",     [("Block Number", 1, _blk), ("Data", 16, _pay)]),
        0x50: ("HALT",      []),
        0x60: ("AUTH_A",    [("Block Number", 1, _blk)]),
        0x61: ("AUTH_B",    [("Block Number", 1, _blk)]),
        0xC0: ("DECREMENT", [("Block Number", 1, _blk), ("Value", 4, _pay)]),
        0xC1: ("INCREMENT", [("Block Number", 1, _blk), ("Value", 4, _pay)]),
        0xC2: ("RESTORE",   [("Block Number", 1, _blk)]),
        0xB0: ("TRANSFER",  [("Block Number", 1, _blk)]),
    }

    def parse_rx(self, data: bytes, tx: bytes = None) -> ParsedFrame | None:
        if not data:
            return None
        # 单字节 ACK/NACK
        if len(data) == 1 and data[0] in self.RESPONSES:
            desc = self.RESPONSES[data[0]]
            label = desc.split("—")[0].strip() if "—" in desc else "Response"
            return ParsedFrame(
                raw=data, label=label,
                fields=[ParsedField("Response", data, data[0], desc)]
            )
        # READ 响应：16 字节 block 数据
        if tx and tx[0] == 0x30 and len(data) == 16:
            return ParsedFrame(
                raw=data, label="BLOCK DATA",
                fields=[ParsedField("Data", data, 0, f"{len(data)} bytes")]
            )
        return None
