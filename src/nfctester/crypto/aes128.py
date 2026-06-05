from Crypto.Cipher import AES
from .base_crypto import BaseCrypto


class AES128Crypto(BaseCrypto):
    """
    AES-128 ECB 实现
    """
    
    def _validate_params(self, indata: bytes, key: bytes):
        # 密钥长度：16 bytes
        if len(key) != 16:
            raise ValueError(f"AES-128 ECB 密钥为 16 字节，当前长度为 {len(key)}")
        
        # 数据块长度：16 bytes
        if len(indata) != 16:
            raise ValueError(f"AES-128 ECB 数据为 16 字节，当前长度为 {len(indata)}")

    def encrypt(self, indata: bytes, key: bytes) -> bytes:
        self._validate_params(indata, key)
        cipher = AES.new(key, AES.MODE_ECB)
        return cipher.encrypt(indata)

    def decrypt(self, indata: bytes, key: bytes) -> bytes:
        self._validate_params(indata, key)
        cipher = AES.new(key, AES.MODE_ECB)
        return cipher.decrypt(indata)