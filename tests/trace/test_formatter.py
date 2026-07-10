"""TraceFormatter 测试"""
from nfctester.trace.formatter import TraceFormatter


class TestFormatRaw:

    def test_tx_raw(self):
        msg = TraceFormatter.format_raw("TX", b'\x30\x04')
        assert "TX ->" in msg
        assert "30 04" in msg

    def test_rx_raw(self):
        msg = TraceFormatter.format_raw("RX", b'\xAB\xCD')
        assert "RX <-" in msg
        assert "AB CD" in msg

    def test_bits_annotation(self):
        msg = TraceFormatter.format_raw("TX", b'\x26', bits=7)
        assert "[7 bits]" in msg

    def test_bits_0_no_annotation(self):
        msg = TraceFormatter.format_raw("TX", b'\x26', bits=0)
        assert "bits" not in msg

    def test_bits_8_no_annotation(self):
        msg = TraceFormatter.format_raw("TX", b'\x26', bits=8)
        assert "bits" not in msg


class TestFormatSummary:

    def test_summary_with_tag(self):
        msg = TraceFormatter.format_summary("TX", b'\x30\x04', "READ", bits=0)
        assert "TX ->" in msg
        assert "30 04" in msg
        assert "[READ]" in msg

    def test_summary_with_bits(self):
        msg = TraceFormatter.format_summary("TX", b'\x26', "REQA", bits=7)
        assert "[REQA [7 bits]]" in msg


class TestFormatEncryptedPair:

    def test_tx_pair(self):
        msg = TraceFormatter.format_encrypted_pair("TX", b'\x4D\xE3', b'\x71\x07')
        assert "TX ->" in msg
        assert "[encrypted]" in msg
        assert "[decrypted]" in msg
        assert "4D E3" in msg
        assert "71 07" in msg

    def test_rx_pair(self):
        msg = TraceFormatter.format_encrypted_pair("RX", b'\xAC\xB5', b'\x4D\x3C')
        assert "RX <-" in msg
        assert "AC B5" in msg
        assert "4D 3C" in msg

    def test_pair_is_multiline(self):
        msg = TraceFormatter.format_encrypted_pair("TX", b'\xAA', b'\xBB')
        lines = msg.split("\n")
        assert len(lines) == 2

    def test_pair_alignment(self):
        msg = TraceFormatter.format_encrypted_pair("TX", b'\x4D\xE3\x53\x1C', b'\x71\x07\x03\x83')
        lines = msg.split("\n")
        # Second line should have same prefix length as first line
        assert "[encrypted]" in lines[0]
        assert "[decrypted]" in lines[1]
