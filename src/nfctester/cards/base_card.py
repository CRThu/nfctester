from abc import ABC, abstractmethod


class BaseCard(ABC):
    """
    加密卡基类 (如 Mifare Classic)
    """

    def __init__(self, reader, uid: bytes):
        self.reader = reader
        self.uid = uid

    @abstractmethod
    def authenticate(self, block_addr: int, key: bytes, key_type: int) -> bool:
        """执行认证逻辑"""
        pass

    @abstractmethod
    def read_block(self, block_addr: int) -> bytes:
        """读取块数据"""
        pass

    @abstractmethod
    def write_block(self, block_addr: int, data: bytes) -> bool:
        """写入块数据"""
        pass

    @abstractmethod
    def increment_block(self, block_addr: int, value: int) -> bool:
        """递增块"""
        pass

    @abstractmethod
    def decrement_block(self, block_addr: int, value: int) -> bool:
        """递减块"""
        pass

    @abstractmethod
    def restore_block(self, block_addr: int) -> bool:
        """恢复块"""
        pass

    @abstractmethod
    def transfer_block(self, block_addr: int) -> bool:
        """传输块"""
        pass