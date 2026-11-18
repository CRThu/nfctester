"""CLRC663 与串口超时机制单元测试"""
import time
from unittest.mock import MagicMock, PropertyMock, patch

from nfctester.drivers.clrc663 import CLRC663
from nfctester.hardware.serial_transport import SerialTransport


class TestSerialTransportTimeout:
    def test_read_caches_timeout_and_restores_default(self):
        """仅在目标超时变更时写入 pyserial.timeout，传 None 时恢复默认超时"""
        fake_ser = MagicMock()
        fake_ser.timeout = 2.0
        fake_ser.read.return_value = b"\x18"

        setter_calls = []
        current_timeout = [2.0]

        def get_to():
            return current_timeout[0]

        def set_to(val):
            setter_calls.append(val)
            current_timeout[0] = val

        type(fake_ser).timeout = PropertyMock(side_effect=lambda *args: set_to(args[0]) if args else get_to())

        with patch("nfctester.hardware.serial_transport.serial.Serial", return_value=fake_ser):
            tp = SerialTransport(port="COM99", timeout=2.0)

        # 连续两次以相同短超时读取，仅触发一次 timeout 切换
        assert tp.read(1, timeout=0.05) == b"\x18"
        assert tp.read(1, timeout=0.05) == b"\x18"
        assert setter_calls == [0.05]

        # 传 None 时切回默认 2.0s
        assert tp.read(1) == b"\x18"
        assert setter_calls == [0.05, 2.0]


class TestCLRC663UARTAndTimeout:
    def test_write_reg_uses_reg_io_timeout_and_checks_echo(self):
        """正常写寄存器使用 REG_IO_TIMEOUT 且回显匹配时不产生 warning"""
        mock_tp = MagicMock()
        mock_tp.read.return_value = b"\x2e"
        mock_trace = MagicMock()
        reader = CLRC663(mock_tp, trace_mgr=mock_trace)

        reader._write_reg(0x2E, 0x08)

        mock_tp.write.assert_called_once_with(b"\x2e\x08")
        mock_tp.read.assert_called_once_with(1, timeout=CLRC663.REG_IO_TIMEOUT)
        mock_trace.warning.assert_not_called()

    def test_write_reg_warns_on_echo_timeout_and_mismatch(self):
        """回显超时与字节不匹配均如实记录 warning"""
        mock_tp = MagicMock()
        mock_trace = MagicMock()
        reader = CLRC663(mock_tp, trace_mgr=mock_trace)

        # 回显超时
        mock_tp.read.return_value = b""
        reader._write_reg(0x02, 0x10)
        assert "timeout" in mock_trace.warning.call_args[0][0].lower()

        # 回显字节不匹配
        mock_trace.reset_mock()
        mock_tp.read.return_value = b"\xfe"
        reader._write_reg(0x28, 0x86)
        assert "mismatch" in mock_trace.warning.call_args[0][0].lower()

    def test_write_reg_skip_echo_when_disabled(self):
        """软复位等场景 wait_echo=False 时不触发串口读取"""
        mock_tp = MagicMock()
        reader = CLRC663(mock_tp, trace_mgr=MagicMock())

        reader._write_reg(CLRC663.REG_COMMAND, CLRC663.CMD_SOFT_RESET, wait_echo=False)

        mock_tp.write.assert_called_once_with(bytes([CLRC663.REG_COMMAND, CLRC663.CMD_SOFT_RESET]))
        mock_tp.read.assert_not_called()

    def test_read_reg_uses_reg_io_timeout(self):
        """读寄存器统一使用 REG_IO_TIMEOUT"""
        mock_tp = MagicMock()
        mock_tp.read.return_value = b"\x18"
        reader = CLRC663(mock_tp, trace_mgr=MagicMock())

        val = reader._read_reg(CLRC663.REG_VERSION)

        assert val == 0x18
        mock_tp.write.assert_called_once_with(b"\xff")
        mock_tp.read.assert_called_once_with(1, timeout=CLRC663.REG_IO_TIMEOUT)

    def test_wait_irq_respects_timeout_and_reuses_reg_io_timeout(self):
        """_wait_irq 统一复用 REG_IO_TIMEOUT 且在到期时及时返回 False"""
        mock_tp = MagicMock()
        mock_tp.read.return_value = b"\x00"
        reader = CLRC663(mock_tp, trace_mgr=MagicMock())

        t0 = time.monotonic()
        ok = reader._wait_irq(CLRC663.IRQ0_RX, timeout=0.03)
        elapsed = time.monotonic() - t0

        assert ok is False
        assert 0.025 <= elapsed < 0.08
        timeouts = [call.kwargs["timeout"] for call in mock_tp.read.call_args_list]
        assert len(timeouts) > 0
        assert all(t == CLRC663.REG_IO_TIMEOUT for t in timeouts)
