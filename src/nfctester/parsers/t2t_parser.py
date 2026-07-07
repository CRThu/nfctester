from .table_parser import TableParser
from .base_parser import ParsedField, ParsedFrame
from .registry import ParserRegistry


def _page(b): return f"Page {b[0]} (byte offset {b[0] * 4})"
def _data(b): return f"{len(b)} bytes"
def _pwd(b): return "4-byte password"
def _pack(b): return "2-byte password ACK"


@ParserRegistry.register(atqa=0x0044, sak=0x00, name="NFC Forum Type 2 Tag")
@ParserRegistry.register(atqa=0x0044, sak=0x08, name="MIFARE Ultralight")
@ParserRegistry.register(atqa=0x0044, sak=0x20, name="MIFARE Plus")
class T2TParser(TableParser):
    """NFC Forum Type 2 Tag 指令层解析器"""

    RESPONSES = {
        0x0A: "ACK — Success",
        0x05: "NACK — Invalid argument",
        0x00: "NACK — Not authenticated / Parity error",
    }

    CMD_TABLE = {
        0x30: ("READ",      [("Page Address", 1, _page)]),
        0xA2: ("WRITE",     [("Page Address", 1, _page), ("Write Data", 4, _data)]),
        0x50: ("HALT",      [("Reserved",     1, lambda _: "Must be 0x00")]),
        0x1B: ("PWD_AUTH",  [("Password",     4, _pwd)]),
        0x3C: ("READ_SIG",  [("Address",      1, lambda _: "Fixed 0x00")]),
        0x60: ("AUTH",      [("Address",      1, _page)]),
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
        # READ 响应：4 或 16 字节页数据
        if tx and tx[0] == 0x30 and len(data) in (4, 16):
            return ParsedFrame(
                raw=data, label="Page Data",
                fields=[ParsedField("Data", data, 0, f"{len(data)} bytes")]
            )
        # READ_SIG 响应：64 字节 ECC 签名
        if tx and tx[0] == 0x3C and len(data) == 64:
            return ParsedFrame(
                raw=data, label="ECC Signature",
                fields=[ParsedField("Signature", data, 0, f"{len(data)} bytes")]
            )
        # PWD_AUTH 响应：2 字节 PACK
        if tx and tx[0] == 0x1B and len(data) == 2:
            return ParsedFrame(
                raw=data, label="PACK",
                fields=[ParsedField("PACK", data, 0, _pack(data))]
            )
        return None
