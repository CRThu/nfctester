import os
import pytest
from nfctester.trace import trace
from nfctester.registry import CardReaderRegistry

def pytest_addoption(parser):
    group = parser.getgroup("nfctester-trace", "CRFT Trace Logging Options")
    group.addoption("--trace-driver", action="store_true", help="Enable driver layer tracing")
    group.addoption("--trace-protocol", action="store_true", help="Enable protocol layer tracing")
    group.addoption("--trace-level", action="store", default=None, help="Set minimum logging level (DEBUG, INFO, etc.)")
    group.addoption("--port", default=None, help="Serial port (default: NFCTESTER_PORT env or COM4)")
    group.addoption("--reader", default=None, help="Reader type (default: NFCTESTER_READER env or clrc663)")

def pytest_configure(config):
    config.addinivalue_line("markers", "mifare: mark tests that require MIFARE hardware")
    config.addinivalue_line("markers", "t2t: mark tests that require Type 2 Tag hardware")
    config.addinivalue_line("markers", "ntag224: mark tests that require NTAG224 card hardware")

    if config.getoption("--trace-driver"):
        trace.set_layer("DRIVER", True)
    if config.getoption("--trace-protocol"):
        trace.set_layer("PROTOCOL", True)

    trace_level = config.getoption("--trace-level")
    if trace_level:
        trace.set_level(trace_level)

@pytest.fixture(scope="session")
def card_reader(request):
    """提供一个初始化好的通用 CardReader 实例。

    通过环境变量 NFCTESTER_PORT / NFCTESTER_READER 或命令行参数 --port / --reader
    指定串口和读卡器类型，默认使用 clrc663 on COM4。
    """
    port = request.config.getoption("--port") or os.environ.get("NFCTESTER_PORT", "COM4")
    reader_type = request.config.getoption("--reader") or os.environ.get("NFCTESTER_READER", "clrc663")

    reader = CardReaderRegistry.create(reader_type, transport="serial", port=port)
    reader.open()

    yield reader

    reader.close()
