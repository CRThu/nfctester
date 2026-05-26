import pytest
from crft.trace import trace

def pytest_addoption(parser):
    group = parser.getgroup("crft-trace", "CRFT Trace Logging Options")
    group.addoption("--trace-driver", action="store_true", help="Enable driver layer tracing")
    group.addoption("--trace-protocol", action="store_true", help="Enable protocol layer tracing")
    group.addoption("--trace-level", action="store", default=None, help="Set minimum logging level (DEBUG, INFO, etc.)")

def pytest_configure(config):
    # 注册 markers
    config.addinivalue_line("markers", "mifare: mark tests that require MIFARE hardware")
    config.addinivalue_line("markers", "t2t: mark tests that require Type 2 Tag hardware")
    config.addinivalue_line("markers", "ntag224: mark tests that require NTAG224 card hardware")
    
    # 应用命令行参数到 trace 管理器
    if config.getoption("--trace-driver"):
        trace.set_layer("DRIVER", True)
    if config.getoption("--trace-protocol"):
        trace.set_layer("PROTOCOL", True)
    
    trace_level = config.getoption("--trace-level")
    if trace_level:
        trace.set_level(trace_level)

from crft.hardware import SerialTransport
from crft.drivers import PN532_HSU

@pytest.fixture(scope="session")
def card_reader():
    """提供一个初始化好的通用 CardReader 实例"""
    transport = SerialTransport(port="COM20")
    reader = PN532_HSU(transport)
    reader.connect()
    
    yield reader
    
    reader.disconnect()