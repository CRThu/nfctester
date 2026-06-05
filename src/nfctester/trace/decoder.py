class FrameDecoder:
    """协议解码策略类"""

    @staticmethod
    def decode_physical(data: bytes) -> dict:
        """解析 PN532 原始帧: [PRE, START, LEN, LCS, TFI, DATA, DCS, POST]"""
        if not data:
            return {}

        res = {"raw_hex": data.hex(' ').upper()}
        
        # 解析 ACK
        if data == b'\x00\x00\xFF\x00\xFF\x00':
            res["type"] = "ACK"
            return res
        # 解析 NACK
        elif data == b'\x00\x00\xFF\xFF\x00\x00':
            res["type"] = "NACK"
            return res

        # 检查是否符合数据帧头: 00 00 FF
        if len(data) >= 8 and data.startswith(b'\x00\x00\xFF'):
            res["type"] = "DATA_FRAME"
            res["PRE"] = "00"
            res["START"] = "00 FF"
            length = data[3]
            res["LEN"] = f"{length:02X}"
            res["LCS"] = f"{data[4]:02X}"
            res["TFI"] = f"{data[5]:02X}"
            
            # 校验和提取数据体
            if len(data) >= 6 + length:
                payload = data[6:6+length-1]
                res["DATA"] = payload.hex(' ').upper()
                res["DCS"] = f"{data[6+length-1]:02X}"
                if len(data) > 6 + length:
                    res["POST"] = f"{data[6+length]:02X}"

        return res

    @staticmethod
    def decode_protocol(data: bytes) -> dict:
        """解析 RFID 卡片交互指令: [CMD, ADR, DATA...]"""
        if not data:
            return {}
        
        res = {"raw_hex": data.hex(' ').upper()}
        # 这里后续可以实现更复杂的 RFID 卡片指令集解析 (Type 2/Type 4/Mifare)
        if len(data) >= 1:
            res["CMD"] = f"{data[0]:02X}"
        if len(data) >= 2:
            res["ADR"] = f"{data[1]:02X}"
        if len(data) > 2:
            res["DATA"] = data[2:].hex(' ').upper()
            
        return res
