from abc import ABC, abstractmethod
from ..drivers.card_reader import TransceiveResult


class BaseTag(ABC):
    """
    RFID 标签基类
    """

    def __init__(self, reader):
        self.reader = reader

    def transceive(self, data: bytes, **kwargs) -> TransceiveResult:
        """透传数据到读卡器"""
        return self.reader.transceive(data, **kwargs)

    @abstractmethod
    def read_page(self, page_addr: int) -> bytes:
        """读取页数据"""
        pass

    @abstractmethod
    def write_page(self, page_addr: int, data: bytes) -> bool:
        """写入页数据"""
        pass
