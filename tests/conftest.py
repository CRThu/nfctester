import os
import pytest
from unittest.mock import MagicMock
from nfctester.trace import trace
from nfctester.registry import CardReaderRegistry
from nfctester.drivers.card_reader import CardInfo, TransceiveBits

def pytest_addoption(parser):
    group = parser.getgroup("nfctester-trace", "Trace Logging Options")
    group.addoption("--trace-layer", default=None, help="Enable layers (comma-separated: driver,debug,protocol,warning,error,app,all)")
    group.addoption("--trace-level", default=None, help="Minimum log level (driver/debug/protocol/warning/error/app)")
    group.addoption("--port", default=None, help="Serial port (default: NFCTESTER_PORT env or COM4)")
    group.addoption("--reader", default=None, help="Reader type (default: NFCTESTER_READER env or clrc663)")

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: pure software unit tests, no hardware required")
    config.addinivalue_line("markers", "hil: hardware-in-the-loop tests, requires connected reader")
    config.addinivalue_line("markers", "mifare: mark tests that require MIFARE hardware")
    config.addinivalue_line("markers", "t2t: mark tests that require Type 2 Tag hardware")
    config.addinivalue_line("markers", "ntag21x: mark tests that require NTAG21x hardware")
    config.addinivalue_line("markers", "ntag224: mark tests that require NTAG224 card hardware")

    trace_arg = config.getoption("--trace-layer")
    if trace_arg:
        trace.filter.level = "driver"
        for name in trace_arg.split(","):
            name = name.strip().lower()
            if name == "all":
                for layer in ["driver", "debug", "protocol", "warning", "error", "app"]:
                    setattr(trace.filter, layer, True)
            elif name:
                setattr(trace.filter, name, True)

    level_arg = config.getoption("--trace-level")
    if level_arg:
        trace.filter.level = level_arg

@pytest.fixture
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

@pytest.fixture
def mock_reader():
    """提供预配置的 mock CardReader，用于单元测试。"""
    reader = MagicMock()
    reader.active.return_value = CardInfo(uid=[0x01, 0x02, 0x03, 0x04], atq=[0x44, 0x00], sak=0x08)
    reader.mf_auth.return_value = True
    type(reader).mf_crypto = MagicMock(return_value=False)
    reader.transceive.return_value = TransceiveBits(data=[0x00], bits=0)
    return reader
