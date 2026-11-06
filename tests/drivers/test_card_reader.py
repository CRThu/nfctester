"""CardReader 基类与通用契约单元测试"""
import pytest
from unittest.mock import MagicMock, patch
from nfctester.drivers.card_reader import CardReader, CardInfo
from nfctester.drivers.pn532_hsu import PN532_HSU
from nfctester.drivers.clrc663 import CLRC663


class FakeReader(CardReader):
    """测试用伪读卡器，可控制 _do_active 返回值"""

    def __init__(self):
        super().__init__()
        self._active_result = None

    @property
    def name(self) -> str:
        return "fake"

    @property
    def fifo_size(self) -> int:
        return 64

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


class TestCardReaderCapabilities:
    def test_properties_contract(self):
        reader = FakeReader()
        assert reader.name == "fake"
        assert reader.fifo_size == 64
        assert reader.lazy_crc is True

    def test_fifo_size_and_name_are_read_only(self):
        reader = FakeReader()
        with pytest.raises(AttributeError):
            reader.name = "other"  # type: ignore
        with pytest.raises(AttributeError):
            reader.fifo_size = 128  # type: ignore

    def test_lazy_crc_setter_resets_cache(self):
        reader = FakeReader()
        reader._tx_crc = True
        reader._rx_crc = True
        reader.lazy_crc = False
        assert reader.lazy_crc is False
        assert reader._tx_crc is None
        assert reader._rx_crc is None


class TestPN532Capabilities:
    def test_pn532_properties(self):
        mock_transport = MagicMock()
        reader = PN532_HSU(mock_transport)
        assert reader.name == "pn532"
        assert reader.fifo_size == 64
        assert reader.lazy_crc is True

    def test_pn532_lazy_crc_skips_redundant_writes(self):
        mock_transport = MagicMock()
        reader = PN532_HSU(mock_transport)
        with patch.object(reader, "_modify_reg") as mock_modify:
            # 首次设置 CRC (True, True) 必须写入
            reader._set_crc(True, True)
            assert mock_modify.call_count == 2
            mock_modify.assert_any_call(0x6302, 0x80, 0x80)
            mock_modify.assert_any_call(0x6303, 0x80, 0x80)

            # 再次设置相同状态，应当命中惰性缓存，不触发任何底层写入
            mock_modify.reset_mock()
            reader._set_crc(True, True)
            mock_modify.assert_not_called()

            # 部分修改：仅 rx 改为 False，只应写 0x6303
            mock_modify.reset_mock()
            reader._set_crc(True, False)
            assert mock_modify.call_count == 1
            mock_modify.assert_called_once_with(0x6303, 0x80, 0x00)

            # 关闭 lazy_crc 时，即使状态相同也必须每次强制写入
            reader.lazy_crc = False
            mock_modify.reset_mock()
            reader._set_crc(True, False)
            assert mock_modify.call_count == 2


class TestCLRC663Capabilities:
    def test_clrc663_properties(self):
        mock_transport = MagicMock()
        reader = CLRC663(mock_transport)
        assert reader.name == "clrc663"
        assert reader.fifo_size == 512
        assert reader.lazy_crc is True

    def test_clrc663_lazy_crc_skips_redundant_writes(self):
        mock_transport = MagicMock()
        reader = CLRC663(mock_transport)
        with patch.object(reader, "_modify_reg") as mock_modify:
            # 首次设置 CRC (True, True) 必须写入
            reader._set_crc(True, True)
            assert mock_modify.call_count == 2
            mock_modify.assert_any_call(reader.REG_TX_CRC_PRESET, 0x01, 0x01)
            mock_modify.assert_any_call(reader.REG_RX_CRC_PRESET, 0x01, 0x01)

            # 再次设置相同状态，应当命中惰性缓存，不触发任何底层写入
            mock_modify.reset_mock()
            reader._set_crc(True, True)
            mock_modify.assert_not_called()

            # 状态变更：改为 (False, False)
            mock_modify.reset_mock()
            reader._set_crc(False, False)
            assert mock_modify.call_count == 2
            mock_modify.assert_any_call(reader.REG_TX_CRC_PRESET, 0x01, 0x00)
            mock_modify.assert_any_call(reader.REG_RX_CRC_PRESET, 0x01, 0x00)

            # 关闭 lazy_crc 时，即使状态相同也必须每次强制写入
            reader.lazy_crc = False
            mock_modify.reset_mock()
            reader._set_crc(False, False)
            assert mock_modify.call_count == 2
