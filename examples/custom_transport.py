"""
自定义 Transport 示例：TCP 传输

演示如何注册一个自定义的 Transport 实现，
用于通过 TCP/IP 连接远程读卡器。
"""
from nfctester.registry import TransportRegistry
from nfctester.hardware.base import Transport


@TransportRegistry.register("tcp")
class TCPTransport(Transport):
    """基于 TCP Socket 的传输实现"""

    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        import socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

    def write(self, data: bytes):
        self.sock.sendall(data)

    def read(self, size: int) -> bytes:
        return self.sock.recv(size)

    def flush_input(self):
        self.sock.setblocking(False)
        try:
            while self.sock.recv(4096):
                pass
        except BlockingIOError:
            pass
        finally:
            self.sock.setblocking(True)

    def close(self):
        self.sock.close()
