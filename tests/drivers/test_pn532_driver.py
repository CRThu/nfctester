"""PN532 HSU 驱动单元测试"""
import pytest
from unittest.mock import MagicMock, patch
from nfctester.drivers.pn532_hsu import PN532_HSU


class TestPN532Close:
    def test_close_skips_inrelease_when_rf_field_is_off(self):
        """当射频场关闭时，close() 不应下发 InRelease (0x52) 避免固件报错"""
        mock_transport = MagicMock()
        reader = PN532_HSU(mock_transport)

        # 模拟 rf_field 为 False (读取寄存器 0x6304 返回 0x00)
        with patch.object(reader, "_read_reg", return_value=0x00):
            with patch.object(reader, "_req") as mock_req:
                reader.close()
                mock_req.assert_not_called()

        mock_transport.close.assert_called_once()
        assert reader.mf_crypto is False

    def test_close_sends_inrelease_when_rf_field_is_on(self):
        """当射频场开启时，close() 正常下发 InRelease (0x52 0x00) 释放目标"""
        mock_transport = MagicMock()
        reader = PN532_HSU(mock_transport)

        # 模拟 rf_field 为 True (读取寄存器 0x6304 返回 0x03)
        with patch.object(reader, "_read_reg", return_value=0x03):
            with patch.object(reader, "_req") as mock_req:
                reader.close()
                mock_req.assert_called_once_with(b"\x52\x00")

        mock_transport.close.assert_called_once()
        assert reader.mf_crypto is False

    def test_close_handles_exception_gracefully(self):
        """close() 在释放失败时不抛出异常，并确保 transport 关闭"""
        mock_transport = MagicMock()
        reader = PN532_HSU(mock_transport)

        with patch.object(reader, "_read_reg", side_effect=RuntimeError("Transport broken")):
            reader.close()

        mock_transport.close.assert_called_once()
