from abc import ABC, abstractmethod
from ..drivers.card_reader import TransceiveBits


class BaseTag(ABC):
    """
    RFID 标签基类
    """

    def __init__(self, reader):
        self.reader = reader

    def transceive(self, data: list[int], **kwargs) -> TransceiveBits:
        """透传数据到读卡器"""
        return self.reader.transceive(data, **kwargs)

    @abstractmethod
    def read_page(self, page_addr: int) -> list[int]:
        """读取页数据"""
        pass

    @abstractmethod
    def write_page(self, page_addr: int, data: list[int]) -> bool:
        """写入页数据"""
        pass
