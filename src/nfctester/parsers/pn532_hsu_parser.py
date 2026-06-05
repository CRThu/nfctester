from .base_parser import BaseParser, ParsedField, ParsedFrame

# ── 查找表 ────────────────────────────────────────────────────────────────────
_TFI_DIR = {0xD4: "Host to Device", 0xD5: "Device to Host"}

_CMDS = {
    0xD4: {
        0x00: "Diagnose",          0x02: "GetFirmwareVersion",
        0x04: "GetGeneralStatus",  0x06: "ReadRegister",
        0x08: "WriteRegister",     0x0C: "WriteGPIO",
        0x14: "SAMConfiguration",  0x16: "PowerDown",
        0x40: "InDataExchange",    0x42: "InCommunicateThru",
        0x4A: "InListPassiveTarget", 0x56: "InAutoPoll",
    },
    0xD5: {
        0x01: "Diagnose Response",          0x03: "GetFirmwareVersion Response",
        0x05: "GetGeneralStatus Response",  0x07: "ReadRegister Response",
        0x09: "WriteRegister Response",     0x0D: "WriteGPIO Response",
        0x15: "SAMConfiguration Response",  0x17: "PowerDown Response",
        0x41: "InDataExchange Response",    0x43: "InCommunicateThru Response",
        0x4B: "InListPassiveTarget Response", 0x57: "InAutoPoll Response",
    },
}

_STATUS = {
}

# 特殊帧字节序列
_ACK  = b'\x00\x00\xFF\x00\xFF\x00'
_NACK = b'\x00\x00\xFF\xFF\x00\x00'

# ACK / NACK 静态字段定义: (name, raw_bytes, value, description)
_ACK_FIELDS = [
    ("PREAMBLE",   b'\x00',      0x00,   "Preamble"),
    ("START CODE", b'\x00\xFF',  0x00FF, "Start of Packet"),
    ("ACK CODE",   b'\x00\xFF',  0x00FF, "ACK"),
    ("POSTAMBLE",  b'\x00',      0x00,   "Postamble"),
]
_NACK_FIELDS = [
    ("PREAMBLE",   b'\x00',      0x00,   "Preamble"),
    ("START CODE", b'\x00\xFF',  0x00FF, "Start of Packet"),
    ("NACK CODE",  b'\xFF\x00',  0xFF00, "NACK"),
    ("POSTAMBLE",  b'\x00',      0x00,   "Postamble"),
]


class PN532HSUParser(BaseParser):
    """PN532 HSU 物理帧解析器（ACK / NACK / Normal Frame）"""

    def can_parse(self, data: bytes) -> bool:
        return (
            data == _ACK
            or data == _NACK
            or (len(data) >= 6 and data[:3] == b'\x00\x00\xFF')
        )

    def parse(self, data: bytes) -> ParsedFrame:
        if data == _ACK:
            return ParsedFrame(raw=data, label="PN532 ACK",
                               fields=[ParsedField(n, r, v, d) for n, r, v, d in _ACK_FIELDS])
        if data == _NACK:
            return ParsedFrame(raw=data, label="PN532 NACK",
                               fields=[ParsedField(n, r, v, d) for n, r, v, d in _NACK_FIELDS])
        return self._parse_normal(data)

    def _parse_normal(self, data: bytes) -> ParsedFrame:
        fields = []
        is_valid = True

        # 固定头: 00 00 FF
        fields.append(ParsedField("FRAME HEADER", data[0:3], 0x0000FF, "Preamble + Start Code"))

        if len(data) < 6:
            return ParsedFrame(raw=data, label="PN532 Frame (Truncated)", fields=fields, is_valid=False)

        length, lcs = data[3], data[4]
        lcs_ok = ((length + lcs) & 0xFF) == 0
        if not lcs_ok:
            is_valid = False

        # FRAME CONTROL (LEN + LCS)，含两个子字段
        fc = ParsedField("FRAME CONTROL", data[3:5], (length << 8) | lcs,
                         f"Length={length}, LCS={'Valid' if lcs_ok else 'INVALID'}")
        fc.children = [
            ParsedField("Length",       data[3:4], length, f"{length} bytes"),
            ParsedField("Length Check", data[4:5], lcs,    "Valid" if lcs_ok else "INVALID"),
        ]
        fields.append(fc)

        # APPLICATION LAYER (TFI + CMD + [STATUS] + Payload)
        app_bytes = data[5:5 + length]
        if len(app_bytes) < 2:
            return ParsedFrame(raw=data, label="PN532 Frame", fields=fields, is_valid=False)

        tfi, cmd = app_bytes[0], app_bytes[1]
        cmd_name = _CMDS.get(tfi, {}).get(cmd, f"Unknown (0x{cmd:02X})")

        app = ParsedField("APPLICATION LAYER", app_bytes, tfi, cmd_name)
        children = [
            ParsedField("Direction", bytes([tfi]), tfi, _TFI_DIR.get(tfi, f"Unknown (0x{tfi:02X})")),
            ParsedField("Command",   bytes([cmd]), cmd, cmd_name),
        ]

        # 响应帧额外解析 Status 字节
        payload_offset = 2
        if tfi == 0xD5 and len(app_bytes) > 2:
            sb = app_bytes[2]
            children.append(ParsedField("Status", bytes([sb]), sb,
                                        _STATUS.get(sb, f"Unknown (0x{sb:02X})")))
            payload_offset = 3

        if len(app_bytes) > payload_offset:
            payload = app_bytes[payload_offset:]
            children.append(ParsedField("Payload Data", payload, payload[0], f"{len(payload)} bytes"))

        app.children = children
        fields.append(app)

        # DCS + POSTAMBLE
        tail_offset = 5 + length
        if len(data) > tail_offset:
            fields.append(ParsedField("DCS", data[tail_offset:tail_offset+1],
                                      data[tail_offset], "Data Checksum"))
        if len(data) > tail_offset + 1:
            fields.append(ParsedField("POSTAMBLE", data[tail_offset+1:tail_offset+2],
                                      data[tail_offset+1], "End of Packet"))

        return ParsedFrame(raw=data, label="PN532 Normal Frame", fields=fields, is_valid=is_valid)
