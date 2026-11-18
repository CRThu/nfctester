import serial
from nfctester.trace import trace
from nfctester.registry import TransportRegistry
from .base import Transport

@TransportRegistry.register("serial")
class SerialTransport(Transport):
    """基于串口的传输实现"""
    def __init__(self, port="COM20", baudrate=115200, timeout: float = 2.0):
        try:
            self._default_timeout = timeout
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            trace.debug(f"成功连接串口: {port}")
        except Exception as e:
            trace.error(f"无法打开串口: {e}")
            raise

    def write(self, data: bytes):
        self.ser.write(data)

    def read(self, size: int, timeout: float | None = None) -> bytes:
        # 仅在超时值变更时下发串口配置，避免热路径重复系统调用
        target = self._default_timeout if timeout is None else timeout
        if target != self.ser.timeout:
            self.ser.timeout = target
        return self.ser.read(size)

    def flush_input(self):
        self.ser.reset_input_buffer()

    @property
    def is_open(self) -> bool:
        return self.ser.is_open

    def close(self):
        if self.ser.is_open:
            self.ser.close()
            trace.debug("串口已关闭")