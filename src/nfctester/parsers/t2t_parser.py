from .table_parser import TableParser
from .base_parser import ParsedField, ParsedFrame
from .registry import ParserRegistry


def _page(b): return f"Page {b[0]} (byte offset {b[0] * 4})"
def _page_range(b): return f"Pages {b[0]}–{b[1]}"
def _data(b): return f"{len(b)} bytes"
def _pwd(b): return "4-byte password"
def _pack(b): return "2-byte password ACK"
def _fixed00(b): return "Fixed 0x00"
def _fixed02(b): return "Fixed 0x02"


@ParserRegistry.register(atqa=0x0044, sak=0x00, name="NFC Forum Type 2 Tag")
@ParserRegistry.register(atqa=0x0044, sak=0x20, name="MIFARE Plus")
class T2TParser(TableParser):
    """NFC Forum Type 2 Tag 指令层解析器

    统一覆盖 NTAG21x、NTAG22x DNA、MIFARE Ultralight、MIFARE Plus 等
    T2T 兼容卡片的命令集。两个协议命令基本一致，NTAG22x DNA 额外支持
    AES-128 三通互认证 (AUTH)。
    """

    RESPONSES = {
        0x0A: "ACK — Success",
        0x05: "NACK — Invalid argument",
        0x00: "NACK — Not authenticated / Parity error",
    }

    CMD_TABLE = {
        0x30: ("READ",          [("Page Address", 1, _page)]),
        0x3A: ("FAST_READ",     [("Start Page", 1, _page), ("End Page", 1, _page)]),
        0xA2: ("WRITE",         [("Page Address", 1, _page), ("Write Data", 4, _data)]),
        0xA0: ("COMPAT_WRITE",  [("Page Address", 1, _page), ("Write Data", 4, _data)]),
        0x50: ("HALT",          []),
        0x60: ("GET_VERSION",   [("Address", 1, _fixed00)]),
        0x39: ("READ_CNT",      [("Address", 1, _fixed02)]),
        0x3C: ("READ_SIG",      [("Address", 1, _fixed00)]),
        0x1B: ("PWD_AUTH",      [("Password", 4, _pwd)]),
        0x1A: ("AUTH",          [("Address", 1, _page)]),
        0xAF: ("AUTH_P2",      []),
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
        # READ / FAST_READ 响应：4 或 16 字节页数据
        if tx and tx[0] in (0x30, 0x3A) and len(data) in (4, 16):
            return ParsedFrame(
                raw=data, label="PAGE DATA",
                fields=[ParsedField("Data", data, 0, f"{len(data)} bytes")]
            )
        # READ_SIG 响应：48 字节 (NTAG22x) 或 64 字节 (NTAG21x) ECC 签名
        if tx and tx[0] == 0x3C and len(data) in (48, 64):
            return ParsedFrame(
                raw=data, label="ECC SIGNATURE",
                fields=[ParsedField("Signature", data, 0, f"{len(data)} bytes")]
            )
        # PWD_AUTH 响应：2 字节 PACK
        if tx and tx[0] == 0x1B and len(data) == 2:
            return ParsedFrame(
                raw=data, label="PACK",
                fields=[ParsedField("PACK", data, 0, _pack(data))]
            )
        # GET_VERSION 响应：9 字节
        if tx and tx[0] == 0x60 and len(data) == 9:
            return ParsedFrame(
                raw=data, label="VERSION INFO",
                fields=[
                    ParsedField("Header", data[0:1], data[0], f"Fixed 0x{data[0]:02X}"),
                    ParsedField("Vendor ID", data[1:2], data[1],
                                f"NXP (0x{data[1]:02X})" if data[1] == 0x04 else f"0x{data[1]:02X}"),
                    ParsedField("Product Type", data[2:3], data[2], f"0x{data[2]:02X}"),
                    ParsedField("Product Subtype", data[3:4], data[3], f"0x{data[3]:02X}"),
                    ParsedField("Major Version", data[4:5], data[4], f"0x{data[4]:02X}"),
                    ParsedField("Minor Version", data[5:6], data[5], f"0x{data[5]:02X}"),
                    ParsedField("Storage Size", data[6:8],
                                int.from_bytes(data[6:8], "big"), f"{len(data[6:8])} bytes"),
                    ParsedField("Protocol Type", data[8:9], data[8], f"0x{data[8]:02X}"),
                ]
            )
        # READ_CNT 响应：3 字节 NFC 计数器
        if tx and tx[0] == 0x39 and len(data) == 3:
            counter = int.from_bytes(data, "big")
            return ParsedFrame(
                raw=data, label="NFC COUNTER",
                fields=[ParsedField("Counter", data, counter, f"{counter}")]
            )
        # AUTH 响应 (NTAG22x DNA mutual auth part 1)：AF + 16 字节加密随机数
        if tx and tx[0] == 0x1A and len(data) == 17 and data[0] == 0xAF:
            return ParsedFrame(
                raw=data, label="AUTH CHALLENGE",
                fields=[
                    ParsedField("Status", data[0:1], data[0], "More data (0xAF)"),
                    ParsedField("Encrypted RndB", data[1:17], 0, "16 bytes"),
                ]
            )
        # AUTH_P2 响应 (NTAG22x DNA mutual auth part 2)：00 + 16 字节加密 RndA'
        if tx and tx[0] == 0xAF and len(data) == 17 and data[0] == 0x00:
            return ParsedFrame(
                raw=data, label="AUTH RESPONSE",
                fields=[
                    ParsedField("Status", data[0:1], data[0], "Success (0x00)"),
                    ParsedField("Encrypted RndA'", data[1:17], 0, "16 bytes"),
                ]
            )
        return None
