from ..registry import CardRegistry
from .base_card import BaseCard


@CardRegistry.register("mifare_classic")
class MifareClassicCard(BaseCard):
    """MIFARE Classic 完整操作实现"""
    
    CMD_READ = 0x30
    CMD_WRITE = 0xA0
    CMD_INCREMENT = 0xC1
    CMD_DECREMENT = 0xC0
    CMD_RESTORE = 0xC2
    CMD_TRANSFER = 0xB0

    def __init__(self, reader):
        super().__init__(reader)

    def _ensure_uid(self):
        if self.uid is not None:
            return
        info = self.reader.active()
        if not info:
            raise RuntimeError("未发现卡片，请确认已放置在读卡器上")
        self.uid = info.uid

    def authenticate(self, block_addr: int, key: list[int], key_type: int = 0x60) -> bool:
        """
        MIFARE Classic 认证
        :param block_addr: 块地址
        :param key: 6 字节密钥
        :param key_type: 0x60 (KeyA) 或 0x61 (KeyB)
        """
        if len(key) != 6:
            raise ValueError("Key must be 6 bytes")
        
        # Mifare 认证需要 UID，未寻卡时自动寻卡
        self._ensure_uid()

        # 使用读卡器提供的 mf_auth (硬件自动封装)
        return self.reader.mf_auth(block_addr, key_type, key, self.uid)

    def increment_block(self, block_addr: int, value: int) -> bool:
        """对块进行递增操作"""
        if not (0 <= value < (1 << 32)):
            raise ValueError("value must be a 32-bit unsigned integer")
        cmd = [self.CMD_INCREMENT, block_addr] + list(value.to_bytes(4, "little"))
        res = self.reader.transceive(cmd)
        return res.data is not None

    def decrement_block(self, block_addr: int, value: int) -> bool:
        """对块进行递减操作"""
        if not (0 <= value < (1 << 32)):
            raise ValueError("value must be a 32-bit unsigned integer")
        cmd = [self.CMD_DECREMENT, block_addr] + list(value.to_bytes(4, "little"))
        res = self.reader.transceive(cmd)
        return res.data is not None

    def restore_block(self, block_addr: int) -> bool:
        """恢复块的临时值"""
        cmd = [self.CMD_RESTORE, block_addr]
        res = self.reader.transceive(cmd)
        return res.data is not None

    def transfer_block(self, block_addr: int) -> bool:
        """将临时值写回块"""
        cmd = [self.CMD_TRANSFER, block_addr]
        res = self.reader.transceive(cmd)
        return res.data is not None

    def read_block(self, block_addr: int) -> list[int]:
        """读取块数据"""
        cmd = [self.CMD_READ, block_addr]
        res = self.reader.transceive(cmd)
        return res.data

    def write_block(self, block_addr: int, data: list[int]) -> bool:
        """写入块数据"""
        if len(data) != 16:
            raise ValueError("Data must be 16 bytes")
        cmd = [self.CMD_WRITE, block_addr] + list(data)
        res = self.reader.transceive(cmd)
        return res.data is not None
