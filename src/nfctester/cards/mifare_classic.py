from .base_card import BaseCard


class MifareClassicCard(BaseCard):
    """MIFARE Classic 完整操作实现"""
    
    CMD_AUTHENT = 0x40
    CMD_READ = 0x30
    CMD_WRITE = 0xA0
    CMD_INCREMENT = 0xC1
    CMD_DECREMENT = 0xC0
    CMD_RESTORE = 0xC2
    CMD_TRANSFER = 0xB0

    def __init__(self, reader, uid: bytes):
        super().__init__(reader, uid)

    def authenticate(self, block_addr: int, key: bytes, key_type: int = 0x60) -> bool:
        """
        MIFARE Classic 认证 (使用 PN532 硬件实现)
        :param block_addr: 块地址
        :param key: 6 字节密钥
        :param key_type: 0x60 (KeyA) 或 0x61 (KeyB)
        """
        if len(key) != 6:
            raise ValueError("Key must be 6 bytes")
        
        # 使用读卡器提供的 exchange (InDataExchange 自动封装)
        res = self.reader.exchange(bytes([key_type, block_addr]) + key + self.uid)
        return res is not None

    def increment_block(self, block_addr: int, value: int) -> bool:
        """对块进行递增操作"""
        if not (0 <= value < (1 << 32)):
            raise ValueError("value must be a 32-bit unsigned integer")
        cmd = bytes([self.CMD_INCREMENT, block_addr]) + value.to_bytes(4, "little")
        res = self.reader.exchange(cmd)
        return res is not None

    def decrement_block(self, block_addr: int, value: int) -> bool:
        """对块进行递减操作"""
        if not (0 <= value < (1 << 32)):
            raise ValueError("value must be a 32-bit unsigned integer")
        cmd = bytes([self.CMD_DECREMENT, block_addr]) + value.to_bytes(4, "little")
        res = self.reader.exchange(cmd)
        return res is not None

    def restore_block(self, block_addr: int) -> bool:
        """恢复块的临时值"""
        cmd = bytes([self.CMD_RESTORE, block_addr])
        res = self.reader.exchange(cmd)
        return res is not None

    def transfer_block(self, block_addr: int) -> bool:
        """将临时值写回块"""
        cmd = bytes([self.CMD_TRANSFER, block_addr])
        res = self.reader.exchange(cmd)
        return res is not None

    def read_block(self, block_addr: int) -> bytes:
        """读取块数据"""
        cmd = bytes([self.CMD_READ, block_addr])
        return self.reader.exchange(cmd)

    def write_block(self, block_addr: int, data: bytes) -> bool:
        """写入块数据"""
        if len(data) != 16:
            raise ValueError("Data must be 16 bytes")
        cmd = bytes([self.CMD_WRITE, block_addr]) + data
        res = self.reader.exchange(cmd)
        return res is not None
