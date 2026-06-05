from .base_crypto import BaseCrypto

class MifareCrypto1(BaseCrypto):
    """
    Mifare Classic Crypto1 算法加解密实现类
    有状态的流加密引擎
    """
    
    def __init__(self):
        self._state = None
    
    # LFSR 奇数和偶数部分的反馈多项式掩码
    LF_POLY_ODD = 0x29CE5C
    LF_POLY_EVEN = 0x870804

    @staticmethod
    def prng_successor(x_int: int, steps: int) -> int:
        """
        Mifare PRNG 后继函数 (算法归口)
        :param x_int: 当前 PRNG 值
        :param steps: 步进次数
        :return: 更新后的 PRNG 值
        """
        x = x_int
        for _ in range(steps):
            x = (x >> 1) | (((x >> 0) ^ (x >> 2) ^ (x >> 3) ^ (x >> 5)) & 1) << 31
        return x & 0xFFFFFFFF

    @staticmethod
    def _bit(x: int, n: int) -> int:
        """获取整数 x 的第 n 位值 (0 或 1)"""
        return (x >> n) & 1

    @staticmethod
    def _parity(x: int) -> int:
        """计算 LFSR 内部特定的奇偶校验位"""
        x ^= x >> 16
        x ^= x >> 8
        x ^= x >> 4
        return MifareCrypto1._bit(0x6996, x & 0xf)

    @staticmethod
    def _filter(x: int) -> int:
        """
        Crypto1 算法的 2 级非线性滤波函数（Filter Function）
        从当前 LFSR 中取出 20 bit，经过多重非线性布尔函数得出 1 bit 密钥流
        """
        f = (0xf22c0 >> (x & 0xf)) & 16
        f |= (0x6c9c0 >> ((x >> 4) & 0xf)) & 8
        f |= (0x3c8b0 >> ((x >> 8) & 0xf)) & 4
        f |= (0x1e458 >> ((x >> 12) & 0xf)) & 2
        f |= (0x0d938 >> ((x >> 16) & 0xf)) & 1
        return MifareCrypto1._bit(0xEC57E80A, f)

    class State:
        """Crypto1 内部 LFSR 状态，模拟底层的硬件移位寄存器"""
        def __init__(self, key: bytes = None, odd: int = None, even: int = None):
            """
            初始化 Crypto1 状态
            :param key: 6 字节 Mifare 密钥 (可选)
            :param odd: 寄存器奇数部分状态 (可选)
            :param even: 寄存器偶数部分状态 (可选)
            """
            self.odd = odd if odd is not None else 0
            self.even = even if even is not None else 0
            
            if key is not None:
                # 将 6 bytes 密钥转为整数 (大端序)
                key_int = int.from_bytes(key, byteorder='big')
                self.odd = 0
                self.even = 0
                # 将 48 位 Mifare 密钥位按照大端与反转顺序交叉分离进入奇/偶寄存器中
                # i 从 47 递减到 1 (步长为 2)
                for i in range(47, -1, -2):
                    self.odd = (self.odd << 1) | MifareCrypto1._bit(key_int, (i - 1) ^ 7)
                    self.even = (self.even << 1) | MifareCrypto1._bit(key_int, i ^ 7)

        def get_filter_bit(self) -> int:
            """获取当前状态下的滤波输出位 (Keystream bit)"""
            return MifareCrypto1._filter(self.odd)

        def _shift(self, bit: int, feedback: bool = True) -> int:
            """
            执行单次移位与混淆 (原子操作)
            :param bit: 输入位 (用于参与反馈或作为输入)
            :param feedback: 是否启用 LFSR 反馈逻辑
            :return: 当前生成的密钥流 bit (ks_bit)
            """
            # 获取当前的滤波输出位作为密钥流位 (在移位前)
            ks_bit = self.get_filter_bit()

            # 基础反馈来自于多项式掩码与当前状态的奇偶校验
            feedin = (MifareCrypto1.LF_POLY_ODD & self.odd) ^ (MifareCrypto1.LF_POLY_EVEN & self.even)
            # 如果开启反馈（即加密/同步模式），则将输入位混入反馈回路
            if feedback:
                feedin ^= bit
            
            # 推入反馈位并确保状态字截断在 32 位界限以内
            new_even = ((self.even << 1) | MifareCrypto1._parity(feedin)) & 0xFFFFFFFF
            self.odd, self.even = new_even, self.odd
            
            return ks_bit

    def initialize(self, key: bytes):
        """
        重新实例化加密状态
        :param key: 6 字节 Mifare 密钥
        """
        self._state = self.State(key=key)

    def encrypt(self, indata: bytes, feedback: bool = True) -> bytes:
        """
        加密数据
        :param indata: 输入原始数据 (bytes)
        :param feedback: 是否启用反馈 (认证 Token 计算时通常为 False)
        :return: 加密后的字节流 (bytes)
        """
        if self._state is None:
            raise RuntimeError("MifareCrypto1 state not initialized. Call initialize() first.")
            
        out = bytearray()
        for p_byte in indata:
            c_byte = 0
            # 在 Mifare 协议中，数据是逐 bit 处理的
            for i in range(8):
                # 1. 提取明文位并执行状态移位
                p_bit = self._bit(p_byte, i)
                ks_bit = self._state._shift(p_bit, feedback=feedback)
                
                # 2. 与流密钥异或得出密文位
                c_bit = p_bit ^ ks_bit
                c_byte |= (c_bit << i)
                
            out.append(c_byte)
        return bytes(out)

    def decrypt(self, indata: bytes, feedback: bool = True) -> bytes:
        """
        解密数据
        :param indata: 输入加密数据 (bytes)
        :param feedback: 是否启用反馈 (解密通常需要反馈以保持同步)
        :return: 解密后的原始字节流 (bytes)
        """
        if self._state is None:
            raise RuntimeError("MifareCrypto1 state not initialized. Call initialize() first.")
            
        out = bytearray()
        for c_byte in indata:
            p_byte = 0
            for i in range(8):
                # 1. 解密时先获取流密钥
                ks_bit = self._state.get_filter_bit()
                
                # 2. 异或密文位得出明文位
                c_bit = self._bit(c_byte, i)
                p_bit = c_bit ^ ks_bit
                p_byte |= (p_bit << i)
                
                # 3. 将明文位混入反馈状态中，保持状态机同步
                self._state._shift(p_bit, feedback=feedback)
                
            out.append(p_byte)
        return bytes(out)
