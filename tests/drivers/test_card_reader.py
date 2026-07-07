"""CardReader 基类模板方法单元测试"""
import pytest
from unittest.mock import patch
from nfctester.drivers.card_reader import CardReader, CardInfo


class FakeReader(CardReader):
    """测试用伪读卡器，可控制 _do_active 返回值"""

    def __init__(self):
        self._active_result = None

    def open(self): pass
    def close(self): pass
    def get_version(self): return [1, 0]
    @property
    def rf_field(self): return False
    @rf_field.setter
    def rf_field(self, v): pass
    @property
    def mf_crypto(self): return False
    def mf_auth(self, block, key_type, key, uid): return False
    def transceive(self, data, last_tx_bits=0, tx_crc=True, rx_crc=True):
        return None

    def _do_active(self):
        return self._active_result


class TestCardReaderActive:
    def test_active_calls_do_active(self):
        reader = FakeReader()
        reader._active_result = CardInfo(uid=[1, 2, 3, 4], atq=[0x04, 0x00], sak=0x08)
        result = reader.active()
        assert result is not None
        assert result.uid == [1, 2, 3, 4]

    def test_active_returns_none_when_no_card(self):
        reader = FakeReader()
        reader._active_result = None
        result = reader.active()
        assert result is None

    @patch("nfctester.trace.manager.TraceManager.set_parser")
    def test_active_sets_parser_on_success(self, mock_set_parser):
        reader = FakeReader()
        reader._active_result = CardInfo(uid=[1, 2, 3, 4], atq=[0x04, 0x00], sak=0x08)
        reader.active()
        mock_set_parser.assert_called_once_with(0x0004, 0x08)

    @patch("nfctester.trace.manager.TraceManager.set_parser")
    def test_active_no_set_parser_when_no_card(self, mock_set_parser):
        reader = FakeReader()
        reader._active_result = None
        reader.active()
        mock_set_parser.assert_not_called()
