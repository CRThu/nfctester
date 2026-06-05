from .base_tag import BaseTag


class Type2Tag(BaseTag):
    """
    NFC Forum Type 2 Tag 标准指令集实现 (如 NTAG21x 系列)
    """

    CMD_READ = 0x30
    CMD_WRITE = 0xA2

    def __init__(self, reader, uid: bytes):
        super().__init__(reader, uid)

    def read_page(self, page_addr: int) -> bytes:
        """
        读取页数据
        T2T READ 指令会返回从 page_addr 开始的 16 字节 (即 4 个页的数据)
        :param page_addr: 页地址
        """
        cmd = bytes([self.CMD_READ, page_addr])
        res = self.transceive(cmd)
        if not res:
            raise RuntimeError(f"Type 2 Tag read_page(0x{page_addr:02X}) failed: No response from card")
        return res

    def write_page(self, page_addr: int, data: bytes):
        """
        写入页数据 (T2T 规范每次写入 4 字节)
        :param page_addr: 页地址
        :param data: 4 字节待写入数据
        """
        if len(data) != 4:
            raise ValueError("Type 2 Tag write_page requires exactly 4 bytes of data")

        cmd = bytes([self.CMD_WRITE, page_addr]) + data
        self.reader.set_crc(True, False)
        res = self.transceive(cmd)
        self.reader.set_crc(True, True)

        if not res:
            raise RuntimeError(f"Type 2 Tag write_page(0x{page_addr:02X}) failed: No response from card")
        if res != b'\x0A':
            raise RuntimeError(f"Type 2 Tag write_page(0x{page_addr:02X}) failed: NAK(0x{res.hex(' ').upper()}) from card")
        
    def read_ndef(self) -> dict:
        """
        读取 NDEF 信息
        逻辑：读取 Page 3 (CC) 获取容量，从 Page 4 开始解析 TLV 结构
        """
        # 1. 读取 CC (Page 3)
        res = self.read_page(3)
        cc = res[:4]
        if cc[0] != 0xE1:
            return {"cc": cc, "ndef": None}
            
        # cc[2] 是数据区大小 (ML), 单位 8 字节
        capacity = cc[2] * 8
        
        # 2. 读取数据区并解析 TLV (从 Page 4 开始)
        data = bytearray()
        # 按照 4 页 (16 字节) 为单位批量读取
        for p in range(4, 4 + (capacity // 4), 4):
            data.extend(self.read_page(p))
            
        ndef = None
        ptr = 0
        while ptr < len(data):
            t = data[ptr]
            if t == 0x00: # NULL TLV
                ptr += 1
                continue
            if t == 0xFE: # Terminator TLV
                break
                
            # 解析 L (长度)
            ptr += 1
            if ptr >= len(data): break
            l = data[ptr]
            ptr += 1
            if l == 0xFF: # 3 字节长度格式
                if ptr + 1 >= len(data): break
                l = (data[ptr] << 8) | data[ptr+1]
                ptr += 2
                
            # 识别 NDEF TLV (0x03)
            if t == 0x03:
                ndef = bytes(data[ptr : ptr + l])
                break
                
            ptr += l
            
        return {
            "cc": cc,
            "capacity": capacity,
            "ndef": ndef
        }
