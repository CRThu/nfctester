"""
自定义 CardReader 示例：ACR122U 读卡器

演示如何注册一个自定义的 CardReader 实现。
继承 CardReader 基类，实现所有抽象方法即可。
"""
from nfctester.registry import CardReaderRegistry
from nfctester.drivers import CardReader


@CardReaderRegistry.register("acr122u")
class ACR122UReader(CardReader):
    """ACR122U 读卡器驱动示例"""

    def __init__(self, transport):
        self.transport = transport

    def connect(self):
        # ACR122U 唤醒与初始化
        self.transport.write(b"\xFF\x00\x00\x00\x00")
        self.transport.flush_input()

    def get_version(self) -> bytes:
        # Get Firmware Version: FF 00 48 00 00
        self.transport.write(b"\xFF\x00\x48\x00\x00")
        return self.transport.read(10)

    def set_crc(self, tx_enabled: bool, rx_enabled: bool):
        pass

    def set_rf_field(self, enabled: bool):
        # LED/Buzzer 控制: FF 00 40 XX 04 ...
        pass

    def get_rf_field(self) -> bool:
        return True

    def find(self) -> dict:
        # Polling: FF 00 00 00 02 D4 4A ...
        cmd = b"\xD4\x4A\x01\x00"
        frame = bytes([0xFF, 0x00, 0x00, 0x00, len(cmd)]) + cmd
        self.transport.write(frame)
        res = self.transport.read(20)
        if res and len(res) >= 10:
            return {"uid": res[6:10], "atq": res[2:4], "sak": res[4]}
        return None

    def select(self) -> dict:
        return self.find()

    def deselect(self) -> bool:
        return True

    def exchange(self, data: bytes) -> bytes:
        # APDU 透传
        frame = bytes([0xFF, 0x00, 0x00, 0x00, len(data)]) + data
        self.transport.write(frame)
        return self.transport.read(262)

    def transceive(self, data: bytes, last_tx_bits: int = 0) -> bytes:
        return self.exchange(data)

    def disconnect(self):
        self.transport.close()
