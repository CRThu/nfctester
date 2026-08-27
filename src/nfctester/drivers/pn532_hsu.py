import time
from .card_reader import CardReader, CardInfo, TransceiveBits
from nfctester.trace import trace
from nfctester.registry import CardReaderRegistry

@CardReaderRegistry.register("pn532")
class PN532_HSU(CardReader):
    """PN532 HSU 协议驱动实现"""
    # PN532 错误码对照表
    PN532_ERRORS = {
        0x01: "超时，目标未响应 (Time Out)",
        0x02: "CIU 检测到 CRC 错误 (CRC Error)",
        0x03: "CIU 检测到奇偶校验错误 (Parity Error)",
        0x04: "防冲突/选择操作期间位计数错误 (Bit Count Error)",
        0x05: "Mifare 操作期间帧错误 (Framing Error)",
        0x06: "106 kbps 逐位防冲突期间检测到异常位冲突 (Bit-collision Error)",
        0x07: "通信缓冲区大小不足 (Buffer Insufficient)",
        0x09: "CIU 检测到 RF 缓冲区溢出 (RF Buffer Overflow)",
        0x0A: "主动通信模式下，对方未及时开启 RF 场 (RF Field Error)",
        0x0B: "RF 协议错误 (RF Protocol Error)",
        0x0D: "温度错误：检测到过热，天线驱动已关闭 (Temperature Error)",
        0x0E: "内部缓冲区溢出 (Internal Buffer Overflow)",
        0x10: "参数无效（范围、格式等） (Invalid Parameter)",
        0x12: "DEP 协议：PN532 不支持接收到的命令 (Command Not Supported)",
        0x13: "数据格式与规范不匹配 (Data Format Mismatch)",
        0x14: "Mifare：认证错误 (Authentication Error)",
        0x23: "ISO14443-3：UID 校验位错误 (UID Check Byte Error)",
        0x25: "DEP 协议：无效的设备状态 (Invalid Device State)",
        0x26: "当前配置下不允许该操作 (Operation Not Allowed)",
        0x27: "由于当前上下文，该命令不可接受 (Command Not Acceptable)",
        0x29: "配置为目标的 PN532 已被其发起者释放 (Target Released)",
        0x2A: "卡片 ID 不匹配（预期的卡片已被更换） (ID Mismatch)",
        0x2B: "先前激活的卡片已消失 (Card Disappeared)",
        0x2C: "发起者与目标的 NFCID3 不匹配 (NFCID3 Mismatch)",
        0x2D: "检测到过流事件 (Over-current Event)",
        0x2E: "DEP 帧中缺失 NAD (NAD Missing)",
    }

    def __init__(self, transport, trace_mgr=trace):
        # 初始化传输层
        self.transport = transport
        self.trace = trace_mgr
        self._mf_crypto_active = False

    # --- 私有辅助方法 (协议具体实现) ---
    def _send_frame(self, data: bytes):
        """封装并发送 NXP 标准帧"""
        # 数据长度 = TFI (1字节) + DATA
        length = len(data) + 1
        # LCS (长度校验和): LEN + LCS = 0x00
        lcs = (256 - length) & 0xFF
        # TFI (方向): 上位机到PN532固定为 0xD4
        tfi = 0xD4
        # DCS (数据校验和): TFI + DATA + DCS = 0x00
        dcs = (256 - (tfi + sum(data))) & 0xFF

        # 帧结构: 00 00 FF [LEN] [LCS] [TFI] [DATA] [DCS] 00
        frame = b'\x00\x00\xFF' + bytes([length]) + bytes([lcs]) + bytes([tfi]) + data + bytes([dcs]) + b'\x00'
        self.transport.write(frame)
        self.trace.driver(tx=frame)

    def _read_frame(self) -> bytes:
        """读取并解析回复帧"""
        # 读取 ACK (00 00 FF 00 FF 00)
        ack = self.transport.read(6)
        if len(ack) > 0:
            self.trace.driver(rx=ack)

        if ack != b'\x00\x00\xff\x00\xff\x00':
            self.transport.flush_input()
            return None

        # 读取数据帧头
        header = self.transport.read(3)  # 00 00 FF
        if len(header) < 3: return None

        length = self.transport.read(1)[0]
        lcs = self.transport.read(1)[0]
        tfi = self.transport.read(1)[0]  # 应为 0xD5
        data = self.transport.read(length - 1)
        dcs = self.transport.read(1)[0]
        post = self.transport.read(1)[0]

        full_frame = header + bytes([length, lcs, tfi]) + data + bytes([dcs, post])
        self.trace.driver(rx=full_frame)

        return data

    def _req(self, data: bytes) -> bytes:
        """统一请求周期：发送 -> 读取 -> 基础响应校验"""
        self._send_frame(data)
        res = self._read_frame()

        if res is None:
            self.trace.error(f"PN532 指令 0x{data[0]:02X} 执行失败")

        return res

    def _read_reg(self, address: int) -> int:
        """私有寄存器读取：0x06 (ReadRegister), ADR_H, ADR_L"""
        cmd = bytes([0x06, (address >> 8) & 0xFF, address & 0xFF])
        res = self._req(cmd)
        if res and len(res) >= 2 and res[0] == 0x07:
            return res[1]
        return None

    def _dump_registers(self) -> dict:
        """读取指定范围的寄存器并以字典形式返回"""
        ranges = [
            (0x6301, 0x630E),
            (0x6311, 0x631F),
            (0x6321, 0x632B),
            (0x632F, 0x633E),
        ]
        results = {}
        for start, end in ranges:
            for addr in range(start, end + 1):
                val = self._read_reg(addr)
                if val is not None:
                    results[hex(addr)] = hex(val)
        return results

    def _write_reg(self, address: int, value: int):
        """私有寄存器写入：0x08 (WriteRegister), ADR_H, ADR_L, VAL"""
        cmd = bytes([0x08, (address >> 8) & 0xFF, address & 0xFF, value & 0xFF])
        self._req(cmd)

    def _modify_reg(self, address: int, mask: int, value: int):
        """
        读-改-写寄存器指定位域。
        :param address: 16 位寄存器地址
        :param mask:    要修改的位掩码（置 1 的位将被写入）
        :param value:   期望写入的值（仅 mask 对应的位生效）
        """
        current = self._read_reg(address)
        if current is None:
            self.trace.error(f"_modify_reg 读取寄存器 0x{address:04X} 失败")
            return
        new_val = (current & ~mask) | (value & mask)
        self._write_reg(address, new_val)

    def _set_crc(self, tx_enabled: bool, rx_enabled: bool):
        """配置 CRC 校验（内部使用）"""
        self._modify_reg(0x6302, 0x80, 0x80 if tx_enabled else 0x00)
        self._modify_reg(0x6303, 0x80, 0x80 if rx_enabled else 0x00)

    # --- CardReader 接口实现 ---

    def open(self):
        wake_cmd = b'\x55\x55\x00\x00\x00\x00\x00\x00\x00\x00\xFF\x03\xFD\xD4\x14\x01\x17\x00'
        self.transport.write(wake_cmd)
        time.sleep(0.1)
        self.transport.flush_input()

        # 配置 SAM 为普通模式
        self._req(b'\x14\x01\x00')

        """
        配置 PN532 寻卡为不重试模式
        CfgItem 0x05: MaxRetries (3 bytes)
        Byte 1: MxRtyATR (默认 0xFF，设为 0x01)
        Byte 2: MxRtyPSL (默认 0x01)
        Byte 3: MxRtyPassiveActivation (设为 0x01，即重试一次，保证卡片多次REQA可成功进入ACTIVE)
        """
        self._req(b'\x32\x05\x01\x01\x01')

        # 配置 Force100ASK (CIU_TxAuto 0x6305, bit 6)
        self._modify_reg(0x6305, 0x40, 0x40)

        # 配置 Initiator 模式 (CIU_Control 0x633C, bit 4)
        self._modify_reg(0x633C, 0x10, 0x10)

        self._mf_crypto_active = False
        self.trace.app("PN532 HSU 初始化成功")

    def close(self):
        try:
            if self.rf_field:
                self._req(b'\x52\x00')
        except Exception:
            pass
        finally:
            self._mf_crypto_active = False
            self.transport.close()

    def get_version(self) -> list[int]:
        return list(self._req(b'\x02'))

    # --- RF 控制 ---

    @property
    def rf_field(self) -> bool:
        """通过读取 0x6304 寄存器判断物理天线驱动状态。"""
        reg_val = self._read_reg(0x6304)
        if reg_val is not None:
            # Bit 1 (Tx2RFEn) | Bit 0 (Tx1RFEn)
            # 只要任意一个驱动使能，物理 RF 场就应处于开启状态
            return (reg_val & 0x03) != 0
        return False

    @rf_field.setter
    def rf_field(self, enabled: bool):
        """
        开关 PN532 的 RF 场。
        :param enabled: True 开启 RF 场，False 关闭 RF 场
        """
        # CfgItem 0x01: RF field
        # Data 0x01: On, 0x00: Off
        cmd = b'\x32\x01' + (b'\x01' if enabled else b'\x00')
        self._req(cmd)
        self.trace.debug(f"PN532 RF 场: {'开启' if enabled else '关闭'}")

    # --- 寻卡 ---

    def _do_active(self) -> CardInfo | None:
        """REQA → anticoll → SELECT"""
        self.transport.flush_input()
        res = self._req(b'\x4A\x01\x00')
        # PN532 响应格式：0xD5 0x4B [NbTg] [Tg1] ...
        if res and len(res) >= 2 and res[0] == 0x4B:
            nb_targets = res[1]
            if nb_targets > 0:
                uid = list(res[7:7+res[6]])
                atq = list(res[3:5][::-1])  # PN532 返回 MSB first，反转为 LSB first
                sak = res[5]
                trace.debug(f"{'uid':<12}: {bytes(uid).hex(' ').upper()}")
                trace.debug(f"{'atq':<12}: {bytes(atq).hex(' ').upper()}")
                trace.debug(f"{'sak':<12}: {hex(sak)}")
                return CardInfo(uid=uid, atq=atq, sak=sak)
        return None

    # --- Mifare ---

    @property
    def mf_crypto(self) -> bool:
        return self._mf_crypto_active

    def mf_auth(self, block: int, key_type: int, key: list[int], uid: list[int]) -> bool:
        """
        Mifare Classic 认证（使用 PN532 硬件实现）。
        认证成功后 mf_crypto 变为 True。
        """
        cmd = bytes([key_type, block]) + bytes(key) + bytes(uid)
        self.trace.protocol(tx=cmd)
        full_cmd = b'\x40\x01' + cmd
        res = self._req(full_cmd)

        if res and len(res) >= 2 and res[0] == 0x41:
            if res[1] == 0x00:
                self._mf_crypto_active = True
                self.trace.protocol(rx=res[2:])
                return True
            else:
                err_msg = self.PN532_ERRORS.get(res[1], "未知错误")
                self.trace.warning(f"Mifare 认证失败: 0x{res[1]:02X} ({err_msg})")
        return False

    # --- 数据交换 ---

    def transceive(self, data: list[int], last_tx_bits: int = 0, tx_crc: bool = True, rx_crc: bool = True, log_protocol: bool = True) -> TransceiveBits:
        """
        与卡片进行数据交换（支持位级发送）。
        mf_crypto 为 True 时使用 InDataExchange（硬件自动加密），
        否则使用 InCommunicateThru（透传）。
        """
        raw = bytes(data)
        if log_protocol:
            self.trace.protocol(tx=raw, tx_bits=last_tx_bits)

        if self._mf_crypto_active:
            # InDataExchange: 自动处理 Mifare Crypto1 加密
            # 0x40 (InDataExchange), 0x01 (Target 1)
            full_cmd = b'\x40\x01' + raw
            res = self._req(full_cmd)
            # 响应格式: 0x41 (Response), Status, [Data]
            if res and len(res) >= 2 and res[0] == 0x41:
                if res[1] == 0x00:
                    if log_protocol:
                        self.trace.protocol(rx=res[2:])
                    return TransceiveBits(data=list(res[2:]), bits=0)
                else:
                    err_msg = self.PN532_ERRORS.get(res[1], "未知错误")
                    self.trace.warning(f"InDataExchange 返回错误: 0x{res[1]:02X} ({err_msg})")
            return TransceiveBits(data=[], bits=0)
        else:
            # InCommunicateThru: 透传模式
            
            # CIU_BitFraming (0x633D) bit[2:0] = TxLastBits
            # 0 = 发送完整字节；非 0 = 最后字节仅发送指定位数
            if last_tx_bits != 0:
                self._modify_reg(0x633D, 0x07, last_tx_bits & 0x07)

            # 0x42 (InCommunicateThru)
            self._set_crc(tx_crc, rx_crc)
            full_cmd = b'\x42' + raw
            res = self._req(full_cmd)

            # 发送后复原 TxLastBits = 0（整字节模式）
            if last_tx_bits != 0:
                self._modify_reg(0x633D, 0x07, 0x00)

            # 读取 CIU_Control (0x633C) bit[2:0] = RxLastBits
            # 最近一次 transceive 收到数据后 RxLastBits[2:0] 的值
            # 0 表示最后一个字节全部有效（即整字节），非 0 表示最后字节有效位数
            ciu_ctrl = self._read_reg(0x633C)
            last_bits = (ciu_ctrl & 0x07) if ciu_ctrl is not None else 0

            # 响应格式: 0x43 (Response), Status, [Data]
            if res and len(res) >= 2 and res[0] == 0x43:
                if res[1] == 0x00:
                    if log_protocol:
                        self.trace.protocol(rx=res[2:], rx_bits=last_bits)
                    return TransceiveBits(data=list(res[2:]), bits=last_bits)
                else:
                    err_msg = self.PN532_ERRORS.get(res[1], "未知错误")
                    self.trace.warning(f"InCommunicateThru 返回错误: 0x{res[1]:02X} ({err_msg})")
                    return TransceiveBits(data=[], bits=last_bits)
