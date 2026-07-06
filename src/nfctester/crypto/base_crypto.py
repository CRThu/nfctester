from abc import ABC, abstractmethod

class BaseCrypto(ABC):
    """
    加解密抽象基类
    """

    @abstractmethod
    def encrypt(self, indata: list[int], key: list[int]) -> list[int]:
        """
        加密数据
        :param indata: 输入原始数据
        :param key: 密钥
        :return: 加密后的数据
        """
        pass

    @abstractmethod
    def decrypt(self, indata: list[int], key: list[int]) -> list[int]:
        """
        解密数据
        :param indata: 输入加密数据
        :param key: 密钥
        :return: 解密后的原始数据
        """
        pass
