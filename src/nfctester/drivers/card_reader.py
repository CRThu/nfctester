from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CardInfo:
    """寻卡结果"""
    uid: list[int]
    atq: list[int]
    sak: int


@dataclass
class TransceiveBits:
    """收发结果"""
    data: list[int]
    bits: int  # 最后字节有效位数，0 = 整字节有效


class CardReader(ABC):
    """
    通用读卡器接口。

    定义了上层业务逻辑（如 NFC 寻卡、加密卡交互）与底层驱动之间的契约。
    """

    # --- 生命周期 ---

    @abstractmethod
    def open(self):
        """
        打开读卡器并完成硬件初始化（如唤醒芯片、配置 SAM）。
        """
        pass

    @abstractmethod
    def close(self):
        """
        关闭读卡器并释放资源。
        """
        pass

    @abstractmethod
    def get_version(self) -> list[int]:
        """
        获取设备的固件版本信息。
        """
        pass

    # --- RF 控制 ---

    @property
    @abstractmethod
    def rf_field(self) -> bool:
        """
        获取物理天线驱动是否处于开启状态。
        :return: True 开启，False 关闭。
        """
        pass

    @rf_field.setter
    @abstractmethod
    def rf_field(self, enabled: bool):
        """
        开启或关闭读卡器的 RF 场。
        :param enabled: True 开启，False 关闭。
        """
        pass

    # --- 寻卡 ---

    def active(self) -> CardInfo | None:
        """
        寻卡操作（REQA → anticoll → SELECT），检测并激活卡片。
        寻卡成功后自动根据 ATQA/SAK 切换协议解析器。
        :return: CardInfo 或 None。
        """
        info = self._do_active()
        if info:
            from nfctester.trace import trace
            atqa = int.from_bytes(info.atq, "little")
            trace.set_parser(atqa, info.sak)
        return info

    @abstractmethod
    def _do_active(self) -> CardInfo | None:
        """
        子类实现实际的寻卡逻辑。
        """
        pass

    # --- Mifare ---

    @property
    @abstractmethod
    def mf_crypto(self) -> bool:
        """
        获取 Mifare 硬件加密引擎是否处于激活状态。
        """
        pass

    @abstractmethod
    def mf_auth(self, block: int, key_type: int, key: list[int], uid: list[int]) -> bool:
        """
        执行 Mifare Classic 认证。
        认证成功后 mf_crypto 变为 True，后续 transceive 自动使用加密通信。
        :param block: 块地址
        :param key_type: 0x60 (KeyA) 或 0x61 (KeyB)
        :param key: 6 字节密钥
        :param uid: 卡片 UID（由 active() 返回的 CardInfo.uid 提供）
        :return: 是否成功
        """
        pass

    # --- 数据交换 ---

    @abstractmethod
    def transceive(self, data: list[int], last_tx_bits: int = 0, tx_crc: bool = True, rx_crc: bool = True, log_protocol: bool = True) -> TransceiveBits:
        """
        与卡片进行数据交换（支持位级发送）。
        当 mf_crypto 为 True 时，自动使用加密通道（如 PN532 InDataExchange）。
        :param data: 要发送的数据
        :param last_tx_bits: 最后一个字节实际发送的位数，0 = 整字节
        :param tx_crc: 是否对发送数据附加 CRC
        :param rx_crc: 是否对接收数据校验 CRC
        :param log_protocol: 是否输出 PROTOCOL 日志，默认 True。False 时由调用方自行记录
        """
        pass
