import time
from .card_reader import CardReader
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
        self.last_rx_bits = 0

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

    # --- CardReader 接口 ---

    def connect(self):
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
        self.set_crc(True, True)
        self._modify_reg(self.REG_DRV_MODE, 0x08, 0x08)
        self.trace.success("CLRC663 connected")

    def get_version(self) -> bytes:
        ver = self._read_reg(self.REG_VERSION)
        return bytes([ver]) if ver is not None else b''

    def set_crc(self, tx_enabled: bool, rx_enabled: bool):
        self._modify_reg(self.REG_TX_CRC_PRESET, 0x01, 0x01 if tx_enabled else 0x00)
        self._modify_reg(self.REG_RX_CRC_PRESET, 0x01, 0x01 if rx_enabled else 0x00)

    def set_rf_field(self, enabled: bool):
        self._modify_reg(self.REG_DRV_MODE, 0x08, 0x08 if enabled else 0x00)

    def get_rf_field(self) -> bool:
        val = self._read_reg(self.REG_DRV_MODE)
        return bool(val & 0x08) if val is not None else False

    def _do_transceive(self, data: bytes) -> bytes | None:
        """底层 Transceive: idle → 等待 RX_IRQ → 读取。"""
        self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
        time.sleep(0.05)
        return self._exec_command(self.CMD_TRANSCEIVE, data, irq=self.IRQ0_RX)

    def _do_anticollision_select(self, sel_cmd: int) -> tuple[bytes, int] | None:
        """
        执行单级抗冲突 + SELECT 流程。

        Args:
            sel_cmd: SELECT 命令字节 (0x93=CL1, 0x95=CL2, 0x97=CL3)

        Returns:
            (uid_5bytes, sak) 或 None。uid_5bytes 含 BCC，首位可能是 0x88 级联标记。
        """
        # Anti-collision (无 CRC)
        self.set_crc(False, False)
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
        self.set_crc(True, True)
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

    def _do_anticollision_select_all(self) -> tuple[bytes, int] | None:
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
        return (bytes(full_uid), sak)

    def find(self) -> dict | None:
        """ISO 14443-A 寻卡: REQA → Anti-collision → SELECT。"""
        try:
            # REQA (7-bit short frame, 无 CRC)
            self.set_crc(False, False)
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
            return {"uid": uid, "atq": atqa, "sak": sak, "raw": uid}
        finally:
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)

    def select(self) -> dict | None:
        """WUPA → 寻卡 (重新选择卡片，包括 HALT 状态)。"""
        try:
            # WUPA (7-bit short frame, 无 CRC)
            self.set_crc(False, False)
            self._write_reg(self.REG_TX_DATA_NUM, 0x0F)
            self._start_command(self.CMD_TRANSCEIVE, bytes([0x52]), set_tx_num=False)
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
            return {"uid": uid, "atq": atqa, "sak": sak, "raw": uid}
        finally:
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)

    def deselect(self) -> bool:
        """发送 HLTA 去选卡片。"""
        self.set_crc(True, True)
        self._start_command(self.CMD_TRANSMIT, bytes([0x50, 0x00]))
        return self._wait_irq(self.IRQ0_TX, 0.1)

    def exchange(self, data: bytes) -> bytes | None:
        """数据交换 (自动 CRC)。"""
        self.trace.protocol(tx=data)
        response = self._do_transceive(data)
        err = self._check_error()
        if err:
            self.trace.warning(f"CLRC663 exchange error: {err}")
        self.trace.protocol(rx=response)
        return response

    def transceive(self, data: bytes, last_tx_bits: int = 0) -> bytes | None:
        """数据透传 (支持位帧控制)。"""
        self.trace.protocol(tx=data)

        use_bit_framing = last_tx_bits not in (0, 8)
        if use_bit_framing:
            self._modify_reg(self.REG_TX_DATA_NUM, 0x07, last_tx_bits & 0x07)

        self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
        time.sleep(0.05)
        self._flush_fifo()
        self._write_reg(self.REG_IRQ0, 0x7F)
        self._write_fifo(data)
        self._write_reg(self.REG_COMMAND, self.CMD_TRANSCEIVE)
        if not self._wait_irq(self.IRQ0_RX):
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
            self._flush_fifo()
            response = None
        else:
            fifo_len = self._read_reg(self.REG_FIFO_LENGTH) or 0
            response = self._read_fifo(fifo_len) if fifo_len > 0 else b''

        rx_ctrl = self._read_reg(self.REG_RX_BIT_CTRL)
        rx_bits = (rx_ctrl & 0x07) if rx_ctrl is not None else 0
        self.last_rx_bits = 8 if rx_bits == 0 else rx_bits

        if use_bit_framing:
            self._modify_reg(self.REG_TX_DATA_NUM, 0x07, 0x00)

        err = self._check_error()
        if err:
            self.trace.warning(f"CLRC663 transceive error: {err}")

        self.trace.protocol(rx=response)
        return response

    def disconnect(self):
        try:
            self.set_rf_field(False)
        except Exception as e:
            self.trace.error(f"Close RF failed: {e}")
        finally:
            self.transport.close()
