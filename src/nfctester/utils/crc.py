def crc_a(data: bytes) -> bytes:
    """
    计算 ISO 14443A CRC (CRC-A)
    :param data: 输入数据字节流
    :return: 2字节的 CRC 校验值 (LSB First)
    """
    w_crc = 0x6363
    for b in data:
        b ^= (w_crc & 0xFF)
        b ^= (b << 4) & 0xFF
        w_crc = ((w_crc >> 8) ^ (b << 8) ^ (b << 3) ^ (b >> 4)) & 0xFFFF
    return bytes([w_crc & 0xFF, (w_crc >> 8) & 0xFF])
