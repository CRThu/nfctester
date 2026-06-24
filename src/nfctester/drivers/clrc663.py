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
    CMD_LPCD = 0x01
    CMD_LOAD_KEY = 0x02
    CMD_MF_AUTHENT = 0x03
    CMD_RECEIVE = 0x05
    CMD_TRANSMIT = 0x06
    CMD_TRANSCEIVE = 0x07
    CMD_LOAD_PROTOCOL = 0x0D
    CMD_READ_RNR = 0x1C
    CMD_SOFT_RESET = 0x1F

    # --- 寄存器地址 ---
    REG_COMMAND = 0x00
    REG_HOST_CTRL = 0x01
    REG_FIFO_CONTROL = 0x02
    REG_WATER_LEVEL = 0x03
    REG_FIFO_LENGTH = 0x04
    REG_FIFO_DATA = 0x05
    REG_IRQ0 = 0x06
    REG_IRQ1 = 0x07
    REG_IRQ0_EN = 0x08
    REG_IRQ1_EN = 0x09
    REG_ERROR = 0x0A
    REG_STATUS = 0x0B
    REG_RX_BIT_CTRL = 0x0C
    REG_RX_COLL = 0x0D
    REG_T0_CONTROL = 0x0F
    REG_T0_RELOAD_HI = 0x10
    REG_T0_RELOAD_LO = 0x11
    REG_DRV_MODE = 0x28
    REG_TX_CRC_PRESET = 0x2C
    REG_RX_CRC_PRESET = 0x2D
    REG_TX_DATA_NUM = 0x2E
    REG_FRAME_CON = 0x33
    REG_RX_CTRL = 0x35
    REG_SERIAL_SPEED = 0x3B
    REG_VERSION = 0x7F

    # --- IRQ0 位定义 ---
    IRQ0_IDLE = 0x10
    IRQ0_TX = 0x08
    IRQ0_RX = 0x04
    IRQ0_ERR = 0x02

    # --- LoadProtocol 协议号 ---
    PROT_ISO14443A = 0x00

    CLRC663_ERRORS = {
        0x01: "数据完整性错误 (IntegErr)",
        0x02: "协议错误 (ProtErr)",
        0x04: "碰撞检测 (CollDet)",
        0x08: "无数据错误 (NoDataErr)",
        0x10: "最小帧错误 (MinFrameErr)",
        0x20: "FIFO 溢出 (FIFOOvl)",
        0x40: "FIFO 写错误 (FiFoWrErr)",
        0x80: "EEPROM 错误 (EE_Err)",
    }

    def __init__(self, transport, trace_mgr=trace):
        self.transport = transport
        self.trace = trace_mgr
        self.last_rx_bits = 0

    # =====================================================================
    # UART 底层协议
    # =====================================================================

    def _uart_write(self, addr: int, value: int):
        """写入单个寄存器。

        地址字节: bits[6:0] = 寄存器地址, bit[7] = 0 (写模式)。
        随后发送数据字节。CLRC663 回传地址字节用于验证。
        """
        addr_byte = addr & 0x7F
        self.transport.write(bytes([addr_byte, value & 0xFF]))
        echo = self.transport.read(1)
        if echo and echo[0] != addr_byte:
            self.trace.warning(f"UART 写回传不匹配: 发送 0x{addr_byte:02X}, 收到 0x{echo[0]:02X}")

    def _uart_read(self, addr: int) -> int | None:
        """读取单个寄存器。

        地址字节: bits[6:0] = 寄存器地址, bit[7] = 1 (读模式)。
        CLRC663 回传数据字节。
        """
        addr_byte = (addr & 0x7F) | 0x80
        self.transport.write(bytes([addr_byte]))
        data = self.transport.read(1)
        return data[0] if len(data) >= 1 else None

    # =====================================================================
    # 寄存器操作
    # =====================================================================

    def _read_reg(self, addr: int) -> int | None:
        return self._uart_read(addr)

    def _write_reg(self, addr: int, value: int):
        self._uart_write(addr, value)

    def _modify_reg(self, addr: int, mask: int, value: int):
        """读-改-写寄存器指定位域。"""
        current = self._read_reg(addr)
        if current is None:
            self.trace.error(f"_modify_reg 读取寄存器 0x{addr:02X} 失败")
            return
        new_val = (current & ~mask) | (value & mask)
        self._write_reg(addr, new_val)

    # =====================================================================
    # FIFO 操作
    # =====================================================================

    def _flush_fifo(self):
        """清空 FIFO 缓冲区。"""
        self._write_reg(self.REG_FIFO_CONTROL, 0x10)

    def _write_fifo(self, data: bytes):
        """将数据写入 FIFO。"""
        for byte in data:
            self._write_reg(self.REG_FIFO_DATA, byte)

    def _read_fifo(self, length: int) -> bytes:
        """从 FIFO 读取指定长度的数据。"""
        result = bytearray()
        for _ in range(length):
            val = self._read_reg(self.REG_FIFO_DATA)
            if val is None:
                break
            result.append(val)
        return bytes(result)

    def _get_fifo_length(self) -> int:
        """获取 FIFO 中的字节数。"""
        val = self._read_reg(self.REG_FIFO_LENGTH)
        return val if val is not None else 0

    # =====================================================================
    # 命令执行
    # =====================================================================

    def _wait_irq(self, mask: int, timeout: float = 0.5) -> bool:
        """等待指定的 IRQ 位被置位。"""
        end_time = time.time() + timeout
        while time.time() < end_time:
            irq0 = self._read_reg(self.REG_IRQ0)
            if irq0 is None:
                continue
            if irq0 & mask:
                return True
        return False

    def _start_command(self, cmd: int, data: bytes = b''):
        """启动命令执行: 清空 FIFO → 设置 TxDataNum → 写入数据 → 清除 IRQ → 写入命令码。"""
        self._flush_fifo()
        self._write_reg(self.REG_TX_DATA_NUM, 0x08)
        if data:
            self._write_fifo(data)
        self._write_reg(self.REG_IRQ0, 0x7F)
        self._write_reg(self.REG_COMMAND, cmd & 0x1F)

    def _start_command_raw(self, cmd: int, data: bytes = b''):
        """启动命令执行 (不设置 TxDataNum, 由调用方预设)。"""
        self._flush_fifo()
        if data:
            self._write_fifo(data)
        self._write_reg(self.REG_IRQ0, 0x7F)
        self._write_reg(self.REG_COMMAND, cmd & 0x1F)

    def _exec_command(self, cmd: int, data: bytes = b'', timeout: float = 0.5) -> bytes | None:
        """执行命令并返回 FIFO 中的响应数据。"""
        self.trace.driver(tx=bytes([cmd]) + data)
        self._start_command(cmd, data)
        if not self._wait_irq(self.IRQ0_IDLE, timeout):
            self.trace.error(f"命令 0x{cmd:02X} 执行超时")
            return None
        fifo_len = self._get_fifo_length()
        if fifo_len > 0:
            response = self._read_fifo(fifo_len)
            self.trace.driver(rx=response)
            return response
        return b''

    # =====================================================================
    # CardReader 接口实现
    # =====================================================================

    def connect(self):
        """初始化 CLRC663: 软复位 → 加载协议 → 启用 CRC → 开启 RF 场。"""
        self.transport.flush_input()
        self._write_reg(self.REG_COMMAND, self.CMD_SOFT_RESET)
        time.sleep(0.05)
        self.transport.flush_input()
        self._flush_fifo()

        res = self._exec_command(self.CMD_LOAD_PROTOCOL, bytes([self.PROT_ISO14443A, self.PROT_ISO14443A]))
        if res is None:
            self.trace.error("LoadProtocol 失败")

        self.set_crc(True, True)
        self._modify_reg(self.REG_DRV_MODE, 0x08, 0x08)
        self.trace.success("CLRC663 初始化成功")

    def get_version(self) -> bytes:
        """读取芯片版本寄存器 (0x7F)。"""
        ver = self._read_reg(self.REG_VERSION)
        return bytes([ver]) if ver is not None else b''

    def set_crc(self, tx_enabled: bool, rx_enabled: bool):
        """配置 CRC 自动处理。"""
        self._modify_reg(self.REG_TX_CRC_PRESET, 0x01, 0x01 if tx_enabled else 0x00)
        self._modify_reg(self.REG_RX_CRC_PRESET, 0x01, 0x01 if rx_enabled else 0x00)

    def set_rf_field(self, enabled: bool):
        """开启或关闭 RF 场。"""
        self._modify_reg(self.REG_DRV_MODE, 0x08, 0x08 if enabled else 0x00)
        self.trace.debug(f"CLRC663 RF 场: {'开启' if enabled else '关闭'}")

    def get_rf_field(self) -> bool:
        """查询 RF 场状态。"""
        val = self._read_reg(self.REG_DRV_MODE)
        return bool(val & 0x08) if val is not None else False

    def find(self) -> dict | None:
        """ISO 14443-A 寻卡: REQA → 抗冲突 → SELECT。"""
        try:
            self.set_crc(False, False)

            # REQA (7-bit short frame, no CRC)
            self._write_reg(self.REG_TX_DATA_NUM, 0x0F)
            self._start_command_raw(self.CMD_TRANSCEIVE, bytes([0x26]))
            if not self._wait_irq(self.IRQ0_RX, timeout=0.1):
                return None
            atqa = self._read_fifo(self._get_fifo_length())
            if len(atqa) < 2:
                return None

            # Anti-collision CL1 (NVB=0x20, no CRC)
            self._write_reg(self.REG_TX_DATA_NUM, 0x08)
            self._start_command_raw(self.CMD_TRANSCEIVE, bytes([0x93, 0x20]))
            if not self._wait_irq(self.IRQ0_RX, timeout=0.1):
                return None
            anticoll = self._read_fifo(self._get_fifo_length())
            if len(anticoll) < 5:
                return None

            uid = anticoll[0:4]
            bcc = anticoll[4]
            calc_bcc = uid[0] ^ uid[1] ^ uid[2] ^ uid[3]
            if bcc != calc_bcc:
                self.trace.error(f"BCC 校验失败: 实际 0x{bcc:02X}, 期望 0x{calc_bcc:02X}")
                return None

            # SELECT CL1 (NVB=0x70, with CRC)
            self.set_crc(True, True)
            self._write_reg(self.REG_TX_DATA_NUM, 0x08)
            self._start_command_raw(self.CMD_TRANSCEIVE, bytes([0x93, 0x70]) + uid + bytes([bcc]))
            if not self._wait_irq(self.IRQ0_RX, timeout=0.1):
                return None
            sak_data = self._read_fifo(self._get_fifo_length())
            if len(sak_data) < 1:
                return None
            sak = sak_data[0]

            trace.debug(f"{'uid':<12}: {uid.hex(' ').upper()}")
            trace.debug(f"{'atq':<12}: {atqa.hex(' ').upper()}")
            trace.debug(f"{'sak':<12}: {hex(sak)}")
            trace.debug(f"{'raw':<12}: {anticoll.hex(' ').upper()}")

            return {"uid": uid, "atq": atqa, "sak": sak, "raw": anticoll}

        finally:
            self._write_reg(self.REG_COMMAND, self.CMD_IDLE)

    def select(self) -> dict | None:
        """WUPA → 抗冲突 → SELECT (重新选择卡片)。"""
        try:
            self.set_crc(False, False)
            self._write_reg(self.REG_TX_DATA_NUM, 0x0F)
            self._start_command_raw(self.CMD_TRANSCEIVE, bytes([0x52]))
            self._wait_irq(self.IRQ0_RX, timeout=0.1)
        except Exception:
            pass
        return self.find()

    def deselect(self) -> bool:
        """发送 HLTA 去选卡片。"""
        self.set_crc(True, True)
        self._start_command(self.CMD_TRANSMIT, bytes([0x50, 0x00]))
        return self._wait_irq(self.IRQ0_TX, timeout=0.1)

    def _transceive_raw(self, data: bytes):
        """底层 Transceive: idle → flush FIFO → 写数据 → 清 IRQ → 启动命令。"""
        self._write_reg(self.REG_COMMAND, self.CMD_IDLE)
        time.sleep(0.05)
        self._flush_fifo()
        self._write_reg(self.REG_TX_DATA_NUM, 0x08)
        self._write_fifo(data)
        self._write_reg(self.REG_IRQ0, 0x7F)
        self._write_reg(self.REG_COMMAND, self.CMD_TRANSCEIVE)

    def exchange(self, data: bytes) -> bytes | None:
        """数据交换 (自动 CRC, 如 PN532 的 InDataExchange)。"""
        self.trace.protocol(tx=data)
        self._transceive_raw(data)
        if not self._wait_irq(self.IRQ0_RX, timeout=0.5):
            return None
        response = self._read_fifo(self._get_fifo_length())
        err = self._read_reg(self.REG_ERROR)
        if err and (err & 0x3F):
            desc = self._decode_error(err)
            self.trace.warning(f"exchange 错误: 0x{err:02X} ({desc})")
        self.trace.protocol(rx=response)
        return response

    def transceive(self, data: bytes, last_tx_bits: int = 0) -> bytes | None:
        """数据透传 (如 PN532 的 InCommunicateThru), 支持位帧控制。"""
        self.trace.protocol(tx=data)

        if last_tx_bits != 0:
            self._modify_reg(self.REG_TX_DATA_NUM, 0x07, last_tx_bits & 0x07)
            self.trace.debug(f"{'LAST_TX_BITS':<12}: {last_tx_bits}")

        self._transceive_raw(data)
        if not self._wait_irq(self.IRQ0_RX, timeout=0.5):
            return None

        rx_bit_ctrl = self._read_reg(self.REG_RX_BIT_CTRL)
        self.last_rx_bits = (rx_bit_ctrl & 0x07) if rx_bit_ctrl is not None else 0

        if self.last_rx_bits != 0:
            self.trace.debug(f"{'LAST_RX_BITS':<12}: {self.last_rx_bits}")

        if last_tx_bits != 0:
            self._modify_reg(self.REG_TX_DATA_NUM, 0x07, 0x00)

        response = self._read_fifo(self._get_fifo_length())
        err = self._read_reg(self.REG_ERROR)
        if err and (err & 0x3F):
            desc = self._decode_error(err)
            self.trace.warning(f"transceive 错误: 0x{err:02X} ({desc})")

        self.trace.protocol(rx=response)
        return response

    def _decode_error(self, err: int) -> str:
        """解码 Error 寄存器位为可读描述。"""
        parts = []
        for bit, desc in self.CLRC663_ERRORS.items():
            if err & bit:
                parts.append(desc)
        return ", ".join(parts) if parts else "未知错误"

    def disconnect(self):
        """关闭 RF 场并断开串口。"""
        try:
            self.set_rf_field(False)
        except Exception as e:
            self.trace.error(f"关闭 RF 场失败: {e}")
        finally:
            self.transport.close()
