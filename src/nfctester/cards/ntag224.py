import os
import secrets
from ..registry import CardRegistry
from .type2tag import Type2Tag
from nfctester.crypto import AES128Crypto
from nfctester.utils import BitOps
from nfctester.trace import trace


@CardRegistry.register("ntag224")
class NTAG224(Type2Tag):
    """
    NXP NTAG224 DNA 系列专用驱动
    """

    KEY_ADDR = 0x40

    CMD_GET_VERSION = 0x60
    CMD_PWD_AUTH_A = 0x1A
    CMD_PWD_AUTH_A_RES = 0xAF
    CMD_PWD_AUTH_B = 0xAF
    CMD_PWD_AUTH_B_RES = 0x00

    def __init__(self, reader):
        super().__init__(reader)

    def get_version(self) -> bytes:
        """
        发送 0x60 指令，获取 8 字节版本信息
        """
        cmd = bytes([self.CMD_GET_VERSION])
        res = self.transceive(cmd)
        return res.data

    def write_key(self, key: bytes):
        """
        写入 16 字节 AES 密钥。
        根据 NTAG224 规范，密钥需以反向字节序写入 Page KEY_ADDR~KEY_ADDR+4
        """
        if len(key) != 16:
            raise ValueError("AES key must be 16 bytes")
        
        # 按照规范，字节序需要反转
        reversed_key = key[::-1]
        for i in range(4):
            page_addr = self.KEY_ADDR + i
            chunk = reversed_key[i*4 : (i+1)*4]
            self.write_page(page_addr, chunk)

    def auth(self, password: bytes):
        """
        发送 0x1A 指令进行密码认证
        认证流程说明：
        1. 发送 0x1A + 0x00。
        2. 接收 0xAF + 16byte ek(RndB)
        3. 发送 0xAF + 32byte ek(RndA || RndB')
        4. 接收 0x00 + 16byte ek(RndA')

        :param password: 16 字节密码
        """
        if len(password) != 16:
            raise ValueError("NTAG224 password must be 16 bytes")

        crypto = AES128Crypto()

        # 1. 获取加密随机数: 发送 0x1A + 0x00
        cmd = bytes([self.CMD_PWD_AUTH_A, 0x00])
        res = self.transceive(cmd)

        if not res.data:
            raise PermissionError("Auth Step 1 failed: No response from tag")
        if res.data[0] != self.CMD_PWD_AUTH_A_RES:
            raise PermissionError(f"Auth Step 1 failed: Expected first byte 0x{self.CMD_PWD_AUTH_A_RES:02X}, got 0x{res.data[0]:02X} (response: {res.data.hex()})")
        if len(res.data) != 17:
            raise PermissionError(f"Auth Step 1 failed: Expected 17 bytes (1 header + 16 ek(RndB)), got {len(res.data)} bytes (response: {res.data.hex()})")

        ek_rndb = res.data[1:]
        trace.debug(f"{'Received ek(RndB)':<25}: {ek_rndb.hex(' ').upper()}")

        # 2. 解密 RndB 并生成 RndA
        rndb = crypto.decrypt(ek_rndb, password)
        rndb_prime = BitOps.rol(rndb)
        trace.debug(f"{'Decrypted RndB':<25}: {rndb.hex(' ').upper()}")
        trace.debug(f"{'Rotated RndB\'':<25}: {rndb_prime.hex(' ').upper()}")

        rnda_env = os.environ.get("DEBUG_NTAG224_RNDA")
        if rnda_env:
            rnda = bytes.fromhex(rnda_env)
        else:
            rnda = secrets.token_bytes(16)
        trace.debug(f"{'Generated RndA':<25}: {rnda.hex(' ').upper()}")

        # 3. 加密 RndA || RndB' (使用 AES-128 ECB 模拟 CBC)
        # Block 1: ek1 = AES_Encrypt(RndA)
        ek1 = crypto.encrypt(rnda, password)
        trace.debug(f"{'Encrypted Block 1 (ek1)':<25}: {ek1.hex(' ').upper()}")

        # Block 2: ek2 = AES_Encrypt(RndB' ^ ek1)
        xor_in = BitOps.xor(rndb_prime, ek1)
        trace.debug(f"{'XOR Input for Block 2':<25}: {xor_in.hex(' ').upper()}")
        ek2 = crypto.encrypt(xor_in, password)
        trace.debug(f"{'Encrypted Block 2 (ek2)':<25}: {ek2.hex(' ').upper()}")

        # 4. 发送 0xAF + ek1 + ek2
        cmd = bytes([self.CMD_PWD_AUTH_B]) + ek1 + ek2
        res = self.transceive(cmd)

        if not res.data:
            raise PermissionError("Auth Step 2 failed: No response from tag")
        if res.data[0] != self.CMD_PWD_AUTH_B_RES:
            raise PermissionError(f"Auth Step 2 failed: Expected first byte 0x{self.CMD_PWD_AUTH_B_RES:02X}, got 0x{res.data[0]:02X} (response: {res.data.hex()})")
        if len(res.data) != 17:
            raise PermissionError(f"Auth Step 2 failed: Expected 17 bytes (1 header + 16 ek(RndA')), got {len(res.data)} bytes (response: {res.data.hex()})")

        ek_rnda_prime = res.data[1:]
        trace.debug(f"{'Received ek(RndA\')':<25}: {ek_rnda_prime.hex(' ').upper()}")

        # 5. 解密并验证 RndA'
        # 根据 NTAG224 手册，此处解密使用 ECB 模式（或 IV 链重置）
        rnda_prime_from_tag = crypto.decrypt(ek_rnda_prime, password)
        expected_rnda_prime = BitOps.rol(rnda)

        trace.debug(f"{'Decrypted RndA\'':<25}: {rnda_prime_from_tag.hex(' ').upper()}")
        trace.debug(f"{'Expected RndA\'':<25}: {expected_rnda_prime.hex(' ').upper()}")

        if rnda_prime_from_tag != expected_rnda_prime:
            raise PermissionError("Authentication failed: RndA verification failed")
