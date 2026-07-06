"""Parser parse_rx(data, tx) 接口测试"""
from nfctester.parsers import T2TParser, MifareClassicParser


class TestT2TParserParseRx:

    def test_parse_rx_ack(self):
        p = T2TParser()
        frame = p.parse_rx(b'\x0A', tx=b'\xA2\x00\x01\x02\x03\x04')
        assert frame is not None
        assert frame.label == "ACK"
        assert "ACK" in frame.fields[0].description

    def test_parse_rx_nack_invalid(self):
        p = T2TParser()
        frame = p.parse_rx(b'\x05')
        assert frame is not None
        assert "NACK" in frame.fields[0].description

    def test_parse_rx_nack_not_authenticated(self):
        p = T2TParser()
        frame = p.parse_rx(b'\x00')
        assert frame is not None
        assert "NACK" in frame.fields[0].description

    def test_parse_rx_read_data_4_bytes(self):
        p = T2TParser()
        frame = p.parse_rx(b'\x01\x02\x03\x04', tx=b'\x30\x00')
        assert frame is not None
        assert frame.label == "Page Data"
        assert "4 bytes" in frame.fields[0].description

    def test_parse_rx_read_data_16_bytes(self):
        p = T2TParser()
        data = bytes(16)
        frame = p.parse_rx(data, tx=b'\x30\x00')
        assert frame is not None
        assert frame.label == "Page Data"
        assert "16 bytes" in frame.fields[0].description

    def test_parse_rx_read_sig(self):
        p = T2TParser()
        data = bytes(64)
        frame = p.parse_rx(data, tx=b'\x3C\x00')
        assert frame is not None
        assert frame.label == "ECC Signature"
        assert "64 bytes" in frame.fields[0].description

    def test_parse_rx_pwd_auth_pack(self):
        p = T2TParser()
        frame = p.parse_rx(b'\xAB\xCD', tx=b'\x1B\x01\x02\x03\x04')
        assert frame is not None
        assert frame.label == "PACK"
        assert "password ACK" in frame.fields[0].description

    def test_parse_rx_unknown_returns_none(self):
        p = T2TParser()
        assert p.parse_rx(b'\xFF') is None

    def test_parse_rx_no_tx_context(self):
        p = T2TParser()
        # ACK/NACK don't need TX context
        frame = p.parse_rx(b'\x0A')
        assert frame is not None

    def test_parse_rx_empty_returns_none(self):
        p = T2TParser()
        assert p.parse_rx(b'') is None

    def test_parse_rx_multi_byte_unknown(self):
        p = T2TParser()
        assert p.parse_rx(b'\xAA\xBB\xCC') is None


class TestMifareClassicParserParseRx:

    def test_parse_rx_ack(self):
        p = MifareClassicParser()
        frame = p.parse_rx(b'\x00')
        assert frame is not None
        assert "ACK" in frame.fields[0].description

    def test_parse_rx_nack(self):
        p = MifareClassicParser()
        frame = p.parse_rx(b'\x01')
        assert frame is not None
        assert "NACK" in frame.fields[0].description

    def test_parse_rx_read_block_data(self):
        p = MifareClassicParser()
        data = bytes(16)
        frame = p.parse_rx(data, tx=b'\x30\x04')
        assert frame is not None
        assert frame.label == "Block Data"
        assert "16 bytes" in frame.fields[0].description

    def test_parse_rx_write_ack_with_tx(self):
        p = MifareClassicParser()
        frame = p.parse_rx(b'\x00', tx=b'\xA0\x04\x01\x02\x03\x04')
        assert frame is not None
        assert "ACK" in frame.fields[0].description

    def test_parse_rx_unknown_returns_none(self):
        p = MifareClassicParser()
        assert p.parse_rx(b'\xFF') is None

    def test_parse_rx_empty_returns_none(self):
        p = MifareClassicParser()
        assert p.parse_rx(b'') is None
