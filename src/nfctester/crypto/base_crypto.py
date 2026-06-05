from abc import ABC, abstractmethod

class BaseCrypto(ABC):
    """
    加解密抽象基类
    """

    @abstractmethod
    def encrypt(self, indata: bytes, key: bytes) -> bytes:
        """
        加密数据
        :param indata: 输入原始数据
        :param key: 密钥
        :return: 加密后的字节流
        """
        pass

    @abstractmethod
    def decrypt(self, indata: bytes, key: bytes) -> bytes:
        """
        解密数据
        :param indata: 输入加密数据
        :param key: 密钥
        :return: 解密后的原始字节流
        """
        pass
