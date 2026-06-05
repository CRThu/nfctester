class BitOps:
    """
    字节级位操作工具类，命名参考汇编指令
    """

    @staticmethod
    def inv(data: bytes) -> bytes:
        """ NOT: 字节数组取反 """
        return bytes(~x & 0xFF for x in data)

    @staticmethod
    def xor(a: bytes, b: bytes) -> bytes:
        """ XOR: 字节数组异或 """
        return bytes(x ^ y for x, y in zip(a, b))

    @staticmethod
    def rol(data: bytes, n: int = 1) -> bytes:
        """ ROL: Rotate Left 循环左移 n 字节 """
        if not data:
            return data
        n %= len(data)
        return data[n:] + data[:n]

    @staticmethod
    def ror(data: bytes, n: int = 1) -> bytes:
        """ ROR: Rotate Right 循环右移 n 字节 """
        if not data:
            return data
        n %= len(data)
        return data[-n:] + data[:-n]

    @staticmethod
    def push(buffer: bytes, buffer_bits: int, data: bytes, data_bits: int = None) -> tuple[bytes, int]:
        """
        向比特流末尾追加数据 (保持左对齐)。
        :param buffer: 原比特流字节数组 (左对齐)
        :param buffer_bits: 原比特流有效位数
        :param data: 待追加的字节数组 (左对齐)
        :param data_bits: 待追加的比特数 (默认为 len(data)*8)
        :return: (新字节数组, 新总比特数)
        """
        if data_bits is None:
            data_bits = len(data) * 8
        if data_bits == 0:
            return buffer, buffer_bits
            
        # 提取当前和新数据有效位 (LSB 对齐)
        v1 = int.from_bytes(buffer, 'little')
        v2 = int.from_bytes(data, 'little') & ((1 << data_bits) - 1)
        
        # 拼接并计算新位数
        res_val = (v2 << buffer_bits) | v1
        res_bits = buffer_bits + data_bits
        
        # 转回左对齐字节
        n_bytes = (res_bits + 7) // 8
        res_buf = res_val.to_bytes(n_bytes, 'little')
        return bytes(res_buf), res_bits

    @staticmethod
    def pop(buffer: bytes, buffer_bits: int, n: int) -> tuple[bytes, bytes, int]:
        """
        从比特流头部提取 n 位。
        :param buffer: 比特流字节数组 (左对齐)
        :param buffer_bits: 比特流有效位数
        :param n: 提取位数
        :return: (提取出的字节, 剩余字节数组, 剩余比特数)
        """
        if n <= 0:
            return b'', buffer, buffer_bits
        if n > buffer_bits:
            raise ValueError(f"Cannot pop {n} bits from {buffer_bits} bits")
            
        val = int.from_bytes(buffer, 'little')
        
        # 1. 提取低位处的 n 位
        ext_val = val & ((1 << n) - 1)
        n_ext = (n + 7) // 8
        ext_bytes = ext_val.to_bytes(n_ext, 'little')
        
        # 2. 计算剩余位
        remaining_bits = buffer_bits - n
        res_val = val >> n
        n_rem = (remaining_bits + 7) // 8
        rem_bytes = res_val.to_bytes(n_rem, 'little')
        
        return bytes(ext_bytes), bytes(rem_bytes), remaining_bits
