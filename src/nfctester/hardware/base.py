from abc import ABC, abstractmethod

class Transport(ABC):
    """
    硬件传输层基类，定义了底层通信所需的基本操作。
    """
    @abstractmethod
    def write(self, data: bytes):
        """
        向硬件发送原始字节数据。
        """
        pass

    @abstractmethod
    def read(self, size: int) -> bytes:
        """
        从硬件读取指定长度的原始字节数据。
        """
        pass

    @abstractmethod
    def flush_input(self):
        """
        清除硬件输入缓冲区。
        """
        pass

    @abstractmethod
    def close(self):
        """
        关闭传输通道并释放资源。
        """
        pass