from .table_parser import TableParser


def _page(b): return f"Page {b[0]} (byte offset {b[0] * 4})"
def _data(b): return f"{len(b)} bytes"
def _pwd(b): return "4-byte password"
def _pack(b): return "2-byte password ACK"


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
