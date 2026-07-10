import time
from .card_reader import CardReader, CardInfo, TransceiveBits
from nfctester.trace import trace
from nfctester.registry import CardReaderRegistry


@CardReaderRegistry.register("clrc663")
class CLRC663(CardReader):
    """CLRC663 UART 协议驱动实现。

    通过串口 (UART) 与 CLRC663 通信，使用寄存器读写和 FIFO 命令机制。
    支持 ISO/IEC 14443A 协议，可无缝替换 PN532 读卡器。
    """

    # --- 命令码 ---
    CMD_IDLE = 0x00
    CMD_TRANSMIT = 0x06
    CMD_TRANSCEIVE = 0x07
    CMD_AUTHENT = 0x0E
    CMD_LOAD_PROTOCOL = 0x0D
    CMD_SOFT_RESET = 0x1F

    # --- 寄存器地址 ---
    REG_COMMAND = 0x00
    REG_FIFO_CONTROL = 0x02
    REG_FIFO_LENGTH = 0x04
    REG_FIFO_DATA = 0x05
    REG_IRQ0 = 0x06
    REG_ERROR = 0x0A
    REG_RX_BIT_CTRL = 0x0C
    REG_DRV_MODE = 0x28
    REG_TX_CRC_PRESET = 0x2C
    REG_RX_CRC_PRESET = 0x2D
    REG_TX_DATA_NUM = 0x2E
    REG_VERSION = 0x7F

    # --- Mifare 认证寄存器 ---
    REG_MF_AUTH_KEYA = 0x40  # Key A 地址
    REG_MF_AUTH_KEYB = 0x60  # Key B 地址
    REG_MF_AUTH_UID = 0x80   # UID 地址
    REG_MF_AUTH_BLOCK = 0x90 # 块号地址
    REG_MF_AUTH_STATUS = 0xA0 # 认证状态

    # --- IRQ0 位定义 ---
    IRQ0_IDLE = 0x10
    IRQ0_TX = 0x08
    IRQ0_RX = 0x04

    # --- LoadProtocol 协议号 ---
    PROT_ISO14443A = 0x00

    CLRC663_ERRORS = {
        0x01: "IntegErr", 0x02: "ProtErr", 0x04: "CollDet",
        0x08: "NoDataErr", 0x10: "MinFrameErr", 0x20: "FIFOOvl",
        0x40: "FiFoWrErr", 0x80: "EE_Err",
    }

    def __init__(self, transport, trace_mgr=trace):
        self.transport = transport
        self.trace = trace_mgr
        self._mf_crypto_active = False

    # --- UART 底层 ---

    def _write_reg(self, addr: int, value: int):
        addr_byte = addr & 0x7F
        self.transport.write(bytes([addr_byte, value & 0xFF]))
        echo = self.transport.read(1)
        if echo and echo[0] != addr_byte:
            self.trace.warning(f"UART echo mismatch: sent 0x{addr_byte:02X}, got 0x{echo[0]:02X}")

    def _read_reg(self, addr: int) -> int | None:
        self.transport.write(bytes([(addr & 0x7F) | 0x80]))
        data = self.transport.read(1)
        return data[0] if data else None

    def _modify_reg(self, addr: int, mask: int, value: int):
        current = self._read_reg(addr)
        if current is not None:
            self._write_reg(addr, (current & ~mask) | (value & mask))

    # --- FIFO 操作 ---

    def _flush_fifo(self):
        self._write_reg(self.REG_FIFO_CONTROL, 0x10)

    def _write_fifo(self, data: bytes):
        for b in data:
            self._write_reg(self.REG_FIFO_DATA, b)

    def _read_fifo(self, length: int) -> bytes:
        result = bytearray()
        for _ in range(length):
            val = self._read_reg(self.REG_FIFO_DATA)
            if val is None:
                break
            result.append(val)
        return bytes(result)

    # --- 命令执行 ---

    def _wait_irq(self, mask: int, timeout: float = 0.5) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            irq = self._read_reg(self.REG_IRQ0)
            if irq is not None and irq & mask:
                return True
        return False

    def _start_command(self, cmd: int, data: bytes = b'', set_tx_num: bool = True):
        self._flush_fifo()
        if set_tx_num:
            self._write_reg(self.REG_TX_DATA_NUM, 0x08)
        if data:
            self._write_fifo(data)
        self._write_reg(self.REG_IRQ0, 0x7F)
        self._write_reg(self.REG_COMMAND, cmd & 0x1F)

    def _exec_command(self, cmd: int, data: bytes = b'', irq: int = None, timeout: float = 0.5) -> bytes | None:
        """启动命令并等待 IRQ 完成，默认等待 IRQ_IDLE。"""
        if irq is None:
            irq = self.IRQ0_IDLE
        self._start_command(cmd, data)
        if not self._wait_irq(irq, timeout):
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
            self._flush_fifo()
            return None
        fifo_len = self._read_reg(self.REG_FIFO_LENGTH) or 0
        return self._read_fifo(fifo_len) if fifo_len > 0 else b''

    def _check_error(self) -> str | None:
        """检查 Error 寄存器，返回错误描述或 None。"""
        err = self._read_reg(self.REG_ERROR)
        if err is None:
            return None
        for bit, desc in self.CLRC663_ERRORS.items():
            if err & bit:
                return desc
        return None

    def _set_crc(self, tx_enabled: bool, rx_enabled: bool):
        """配置 CRC（内部使用）

        CLRC663 CRC 控制位:
        - TxCRCPreset (0x2C) bit 0 = TxCRCEn
        - RxCRCPreset (0x2D) bit 0 = RxCRCEn
        """
        self._modify_reg(self.REG_TX_CRC_PRESET, 0x01, 0x01 if tx_enabled else 0x00)
        self._modify_reg(self.REG_RX_CRC_PRESET, 0x01, 0x01 if rx_enabled else 0x00)

    # --- CardReader 接口 ---

    def open(self):
        self.transport.flush_input()
        self._write_reg(self.REG_COMMAND, self.CMD_SOFT_RESET)
        time.sleep(0.05)
        self.transport.flush_input()
        self._flush_fifo()
        result = self._exec_command(
            self.CMD_LOAD_PROTOCOL,
            bytes([self.PROT_ISO14443A, self.PROT_ISO14443A]),
        )
        if result is None:
            raise RuntimeError("CLRC663 LoadProtocol ISO14443A failed")
        self._set_crc(True, True)
        self._modify_reg(self.REG_DRV_MODE, 0x08, 0x08)
        self._mf_crypto_active = False
        self.trace.success("CLRC663 connected")

    def close(self):
        try:
            self.rf_field = False
        except Exception as e:
            self.trace.error(f"Close RF failed: {e}")
        finally:
            self.transport.close()

    def get_version(self) -> list[int]:
        ver = self._read_reg(self.REG_VERSION)
        return [ver] if ver is not None else []

    # --- RF 控制 ---

    @property
    def rf_field(self) -> bool:
        val = self._read_reg(self.REG_DRV_MODE)
        return bool(val & 0x08) if val is not None else False

    @rf_field.setter
    def rf_field(self, enabled: bool):
        self._modify_reg(self.REG_DRV_MODE, 0x08, 0x08 if enabled else 0x00)

    # --- 寻卡 ---

    def _do_anticollision_select(self, sel_cmd: int) -> tuple[bytes, int] | None:
        """
        执行单级抗冲突 + SELECT 流程。

        Args:
            sel_cmd: SELECT 命令字节 (0x93=CL1, 0x95=CL2, 0x97=CL3)

        Returns:
            (uid_5bytes, sak) 或 None。uid_5bytes 含 BCC，首位可能是 0x88 级联标记。
        """
        # Anti-collision (无 CRC)
        self._set_crc(False, False)
        self._write_reg(self.REG_TX_DATA_NUM, 0x08)
        self._start_command(self.CMD_TRANSCEIVE, bytes([sel_cmd, 0x20]), set_tx_num=False)
        if not self._wait_irq(self.IRQ0_RX, 0.1):
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
            self._flush_fifo()
            return None
        anticoll = self._read_fifo(self._read_reg(self.REG_FIFO_LENGTH) or 0)
        if len(anticoll) < 5:
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
            self._flush_fifo()
            return None

        uid = anticoll[:4]
        bcc = anticoll[4]
        if bcc != (uid[0] ^ uid[1] ^ uid[2] ^ uid[3]):
            err = self._check_error()
            self.trace.error(f"BCC check failed (err={err})")
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
            self._flush_fifo()
            return None

        # SELECT (带 CRC)
        self._set_crc(True, True)
        self._write_reg(self.REG_TX_DATA_NUM, 0x08)
        self._start_command(
            self.CMD_TRANSCEIVE,
            bytes([sel_cmd, 0x70]) + uid + bytes([bcc]),
            set_tx_num=False,
        )
        if not self._wait_irq(self.IRQ0_RX, 0.1):
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
            self._flush_fifo()
            return None
        sak_data = self._read_fifo(self._read_reg(self.REG_FIFO_LENGTH) or 0)
        if not sak_data:
            return None

        return (anticoll, sak_data[0])

    def _do_anticollision_select_all(self) -> tuple[list[int], int] | None:
        """
        执行完整抗冲突 + SELECT 流程，自动处理级联 (CL1→CL2→CL3)。

        Returns:
            (full_uid, sak) 或 None。
        """
        full_uid = bytearray()
        sak = 0
        for sel_cmd in [0x93, 0x95, 0x97]:
            result = self._do_anticollision_select(sel_cmd)
            if result is None:
                return None
            anticoll, sak = result
            is_cascade = (anticoll[0] == 0x88)
            if is_cascade:
                full_uid.extend(anticoll[1:4])
            else:
                full_uid.extend(anticoll[:4])
                break
        return (list(full_uid), sak)

    def _do_active(self) -> CardInfo | None:
        """ISO 14443-A 寻卡: REQA → Anti-collision → SELECT"""
        try:
            # REQA (7-bit short frame, 无 CRC)
            self._set_crc(False, False)
            self._write_reg(self.REG_TX_DATA_NUM, 0x0F)
            self._start_command(self.CMD_TRANSCEIVE, bytes([0x26]), set_tx_num=False)
            if not self._wait_irq(self.IRQ0_RX, 0.1):
                self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
                self._flush_fifo()
                return None
            atqa = self._read_fifo(self._read_reg(self.REG_FIFO_LENGTH) or 0)
            if len(atqa) < 2:
                return None

            result = self._do_anticollision_select_all()
            if result is None:
                return None
            uid, sak = result
            return CardInfo(uid=uid, atq=list(atqa), sak=sak)
        finally:
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)

    # --- Mifare ---

    @property
    def mf_crypto(self) -> bool:
        return self._mf_crypto_active

    def mf_auth(self, block: int, key_type: int, key: list[int], uid: list[int]) -> bool:
        """
        Mifare Classic 认证（使用 CLRC663 硬件 MFAuthent 命令）。
        认证成功后 mf_crypto 变为 True，后续 transceive 自动加密。
        """
        # CLRC663 MFAuthent 需要先加载密钥到 Key RAM
        # key_type: 0x60 = Key A (地址 0x40), 0x61 = Key B (地址 0x60)
        if key_type == 0x60:
            key_ram_addr = self.REG_MF_AUTH_KEYA
        else:
            key_ram_addr = self.REG_MF_AUTH_KEYB

        # 写入 6 字节密钥到 Key RAM
        for i, b in enumerate(key):
            self._write_reg(key_ram_addr + i, b)

        # 写入 4 字节 UID 到 UID RAM
        uid_4 = uid[:4]
        for i, b in enumerate(uid_4):
            self._write_reg(self.REG_MF_AUTH_UID + i, b)

        # 写入块号
        self._write_reg(self.REG_MF_AUTH_BLOCK, block)

        # 执行 MFAuthent 命令
        self._write_reg(self.REG_IRQ0, 0x7F)
        self._write_reg(self.REG_COMMAND, self.CMD_AUTHENT)

        if not self._wait_irq(self.IRQ0_IDLE, 0.5):
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
            self.trace.warning("Mifare 认证超时")
            return False

        # 检查认证状态
        status = self._read_reg(self.REG_MF_AUTH_STATUS)
        if status is not None and (status & 0x01):
            self._mf_crypto_active = True
            return True

        self.trace.warning("Mifare 认证失败")
        return False

    # --- 数据交换 ---

    def transceive(self, data: list[int], last_tx_bits: int = 0, tx_crc: bool = True, rx_crc: bool = True, log_protocol: bool = True) -> TransceiveBits:
        """数据交换（支持位级发送 + CRC 控制）"""
        raw = bytes(data)
        if log_protocol:
            self.trace.protocol(tx=raw, tx_bits=last_tx_bits)

        use_bit_framing = last_tx_bits not in (0, 8)
        if use_bit_framing:
            self._modify_reg(self.REG_TX_DATA_NUM, 0x07, last_tx_bits & 0x07)

        self._set_crc(tx_crc, rx_crc)
        self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
        time.sleep(0.05)
        result = self._do_transceive(raw, log_protocol=log_protocol)

        if use_bit_framing:
            self._modify_reg(self.REG_TX_DATA_NUM, 0x07, 0x00)

        return result

    def _do_transceive(self, data: bytes, log_protocol: bool = True) -> TransceiveBits:
        """底层 Transceive 执行"""
        self._flush_fifo()
        self._write_reg(self.REG_IRQ0, 0x7F)
        self._write_fifo(data)
        self._write_reg(self.REG_COMMAND, self.CMD_TRANSCEIVE)

        if not self._wait_irq(self.IRQ0_RX):
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
            self._flush_fifo()
            return TransceiveBits(data=[], bits=0)

        fifo_len = self._read_reg(self.REG_FIFO_LENGTH) or 0
        response = self._read_fifo(fifo_len) if fifo_len > 0 else b''

        self._write_reg(self.REG_COMMAND, self.CMD_IDLE)

        # 读取 RxBitCtrl (0x0C) bit[2:0] = RxLastBits
        # 0 表示最后一个字节全部有效（即整字节），非 0 表示最后字节有效位数
        rx_ctrl = self._read_reg(self.REG_RX_BIT_CTRL)
        last_bits = (rx_ctrl & 0x07) if rx_ctrl is not None else 0

        err = self._check_error()
        if err:
            self.trace.warning(f"CLRC663 transceive error: {err}")

        if log_protocol:
            self.trace.protocol(rx=response, rx_bits=last_bits)
        return TransceiveBits(data=list(response), bits=last_bits)
