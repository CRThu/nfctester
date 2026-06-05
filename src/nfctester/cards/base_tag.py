from abc import ABC, abstractmethod


class BaseTag(ABC):
    """
    RFID 标签基类
    """

    def __init__(self, reader, uid: bytes):
        self.reader = reader
        self.uid = uid

    def transceive(self, data: bytes) -> bytes:
        """透传数据到读卡器"""
        return self.reader.transceive(data)

    @abstractmethod
    def read_page(self, page_addr: int) -> bytes:
        """读取页数据"""
        pass

    @abstractmethod
    def write_page(self, page_addr: int, data: bytes) -> bool:
        """写入页数据"""
        pass
