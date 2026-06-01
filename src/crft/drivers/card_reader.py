from abc import ABC, abstractmethod

class CardReader(ABC):
    """
    通用读卡器接口。
    
    定义了上层业务逻辑（如 NFC 寻卡、加密卡交互）与底层驱动之间的契约。
    """
    @abstractmethod
    def connect(self):
        """
        建立连接并完成硬件初始化（如唤醒芯片、配置 SAM）。
        """
        pass

    @abstractmethod
    def get_version(self) -> bytes:
        """
        获取设备的固件版本信息。
        """
        pass

    @abstractmethod
    def set_crc(self, tx_enabled: bool, rx_enabled: bool):
        """
        配置 CRC 自动处理
        :param tx_enabled: 是否开启自动封装 CRC
        :param rx_enabled: 是否开启自动解析 CRC
        """
        pass

    @abstractmethod
    def set_rf_field(self, enabled: bool):
        """
        开启或关闭读卡器的 RF 场。
        :param enabled: True 开启，False 关闭。
        """
        pass

    @abstractmethod
    def get_rf_field(self) -> bool:
        """
        获取物理天线驱动是否处于开启状态。
        :return: True 开启，False 关闭。
        """
        pass


    @abstractmethod
    def find(self) -> dict:
        """
        寻卡操作（检测并激活卡片为活跃 Target 资源）。
        
        :return: 包含卡片标识（UID）和类型（SAK）的字典。
        """
        pass

    @abstractmethod
    def select(self) -> dict:
        """
        唤醒并重新选择卡片（重新寻卡激活Target 资源，发送WUPA）。
        
        :return: 包含卡片信息的字典，失败时返回 None。
        """
        pass

    @abstractmethod
    def deselect(self) -> bool:
        """
        去选卡片（逻辑去选 Target 资源，发送HLTA）。
        
        :return: 是否成功。
        """
        pass

    def exchange(self, data: bytes) -> bytes:
        """
        与卡片进行数据交换（自动处理读卡器的封装格式，如 PN532 的 InDataExchange）。
        返回卡片返回的原始数据块，如果失败则返回 None。
        """

    @abstractmethod
    def transceive(self, data: bytes, last_tx_bits: int = 0) -> bytes:
        """
        与卡片进行数据透传（如 PN532 的 InCommunicateThru）。
        :param data: 要发送的数据
        :param last_tx_bits: 最后一个字节实际发送的位数，默认 0（整字节）；
                             非 0 时驱动层需配置硬件寄存器，发送后自动复原。
        返回卡片返回的原始数据块，如果失败则返回 None。
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        释放读卡器资源并断开连接。
        """
        pass
