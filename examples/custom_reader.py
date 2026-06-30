"""
自定义 CardReader 示例：ACR122U 读卡器

演示如何注册一个自定义的 CardReader 实现。
继承 CardReader 基类，实现所有抽象方法即可。
"""
from nfctester.registry import CardReaderRegistry
from nfctester.drivers import CardReader
from nfctester.drivers.card_reader import CardInfo, TransceiveResult


@CardReaderRegistry.register("acr122u")
class ACR122UReader(CardReader):
    """ACR122U 读卡器驱动示例"""

    def __init__(self, transport):
        self.transport = transport
        self._mf_crypto_active = False
        self._uid = None

    def open(self):
        # ACR122U 唤醒与初始化
        self.transport.write(b"\xFF\x00\x00\x00\x00")
        self.transport.flush_input()

    def close(self):
        self.transport.close()

    def get_version(self) -> bytes:
        # Get Firmware Version: FF 00 48 00 00
        self.transport.write(b"\xFF\x00\x48\x00\x00")
        return self.transport.read(10)

    @property
    def rf_field(self) -> bool:
        return True

    @rf_field.setter
    def rf_field(self, enabled: bool):
        # LED/Buzzer 控制: FF 00 40 XX 04 ...
        pass

    def active(self) -> CardInfo | None:
        # Polling: FF 00 00 00 02 D4 4A ...
        cmd = b"\xD4\x4A\x01\x00"
        frame = bytes([0xFF, 0x00, 0x00, 0x00, len(cmd)]) + cmd
        self.transport.write(frame)
        res = self.transport.read(20)
        if res and len(res) >= 10:
            uid = res[6:10]
            self._uid = uid
            return CardInfo(uid=uid, atq=res[2:4], sak=res[4])
        return None

    def wakeup(self) -> CardInfo | None:
        return self.active()

    def halt(self) -> bool:
        return True

    @property
    def mf_crypto(self) -> bool:
        return self._mf_crypto_active

    def mf_auth(self, block: int, key_type: int, key: bytes, uid: bytes) -> bool:
        self._mf_crypto_active = True
        return True

    def transceive(self, data: bytes, tx_crc: bool = True, rx_crc: bool = True) -> TransceiveResult:
        # APDU 透传
        frame = bytes([0xFF, 0x00, 0x00, 0x00, len(data)]) + data
        self.transport.write(frame)
        res = self.transport.read(262)
        return TransceiveResult(data=res, rx_bits=0)

    def transceive_bits(self, data: bytes, last_tx_bits: int = 0, tx_crc: bool = True, rx_crc: bool = True) -> TransceiveResult:
        return self.transceive(data, tx_crc=tx_crc, rx_crc=rx_crc)
