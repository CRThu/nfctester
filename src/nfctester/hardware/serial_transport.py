import serial
from nfctester.trace import trace
from nfctester.registry import TransportRegistry
from .base import Transport

@TransportRegistry.register("serial")
class SerialTransport(Transport):
    """基于串口的传输实现"""
    def __init__(self, port="COM20", baudrate=115200):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=0.1)
            trace.debug(f"成功连接串口: {port}")
        except Exception as e:
            trace.error(f"无法打开串口: {e}")
            raise

    def write(self, data: bytes):
        self.ser.write(data)

    def read(self, size: int) -> bytes:
        return self.ser.read(size)

    def flush_input(self):
        self.ser.reset_input_buffer()

    def close(self):
        if self.ser.is_open:
            self.ser.close()
            trace.debug("串口已关闭")