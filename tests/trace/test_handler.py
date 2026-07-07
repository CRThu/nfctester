"""TraceHandler sink + TX/RX 解析路径测试"""
from unittest.mock import MagicMock
from nfctester.trace.handler import TraceHandler, TraceEvent


def _make_handler(**kwargs):
    return TraceHandler(
        layer_name="PROTOCOL",
        logger_func=MagicMock(),
        **kwargs,
    )


class TestSinkCallback:

    def test_sink_receives_event(self):
        sink = MagicMock()
        h = _make_handler()
        h.add_sink(sink)
        h(tx=b'\x30\x04')
        sink.assert_called_once()
        event = sink.call_args[0][0]
        assert isinstance(event, TraceEvent)
        assert event.layer == "PROTOCOL"
        assert event.direction == "TX"
        assert event.raw == b'\x30\x04'
        assert event.formatted is not None

    def test_remove_sink(self):
        sink = MagicMock()
        h = _make_handler()
        h.add_sink(sink)
        h.remove_sink(sink)
        h(tx=b'\x30\x04')
        sink.assert_not_called()

    def test_sink_exception_does_not_propagate(self):
        def bad_sink(event):
            raise RuntimeError("oops")
        h = _make_handler()
        h.add_sink(bad_sink)
        h(tx=b'\x30\x04')

    def test_multiple_sinks(self):
        s1, s2 = MagicMock(), MagicMock()
        h = _make_handler()
        h.add_sink(s1)
        h.add_sink(s2)
        h(tx=b'\x30\x04')
        s1.assert_called_once()
        s2.assert_called_once()

    def test_sink_not_called_without_sinks(self):
        h = _make_handler()
        h(tx=b'\x30\x04')
        h.logger_func.assert_called_once()

    def test_sink_receives_rx_event(self):
        sink = MagicMock()
        h = _make_handler()
        h.add_sink(sink)
        h(rx=b'\xAB\xCD')
        sink.assert_called_once()
        event = sink.call_args[0][0]
        assert event.direction == "RX"
        assert event.raw == b'\xAB\xCD'


class TestTXParsing:

    def test_parse_level_0_uses_raw(self):
        h = _make_handler(parse_level=0)
        h(tx=b'\x30\x04')
        h.logger_func.assert_called_once()
        msg = h.logger_func.call_args[0][0]
        assert "30 04" in msg

    def test_parse_level_1_uses_summary(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=1)
        h(tx=b'\x30\x04')
        msg = h.logger_func.call_args[0][0]
        assert "READ" in msg

    def test_unknown_command_uses_raw(self):
        h = _make_handler(parsers=[], parse_level=1)
        h(tx=b'\xFF\x04')
        msg = h.logger_func.call_args[0][0]
        assert "FF 04" in msg


class TestRXParsing:

    def test_rx_with_tx_context_ack(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=1)
        h(tx=b'\xA2\x00\x01\x02\x03\x04')
        h(rx=b'\x0A')
        assert h.logger_func.call_count == 2
        rx_msg = h.logger_func.call_args_list[1][0][0]
        assert "ACK" in rx_msg

    def test_rx_with_tx_context_read_data(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=1)
        h(tx=b'\x30\x00')
        h(rx=b'\x01\x02\x03\x04')
        assert h.logger_func.call_count == 2
        rx_msg = h.logger_func.call_args_list[1][0][0]
        assert "PAGE DATA" in rx_msg

    def test_rx_unknown_data_falls_back_to_raw(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=1)
        h(rx=b'\xAB\xCD\xEF')
        msg = h.logger_func.call_args[0][0]
        assert "AB CD EF" in msg

    def test_rx_mifare_ack_response(self):
        from nfctester.parsers import MifareClassicParser
        h = _make_handler(parsers=[MifareClassicParser()], parse_level=1)
        h(rx=b'\x00')
        msg = h.logger_func.call_args[0][0]
        assert "ACK" in msg

    def test_rx_direction_triggers_response_path(self):
        sink = MagicMock()
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=1)
        h.add_sink(sink)
        h(rx=b'\x0A')
        event = sink.call_args[0][0]
        assert event.direction == "RX"
        assert event.parsed is not None

    def test_rx_parse_level_0_always_raw(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=0)
        h(rx=b'\x0A')
        msg = h.logger_func.call_args[0][0]
        assert "0A" in msg

    def test_rx_no_parser_falls_back_to_raw(self):
        h = _make_handler(parsers=[], parse_level=1)
        h(rx=b'\x0A')
        msg = h.logger_func.call_args[0][0]
        assert "0A" in msg

    def test_last_tx_recorded(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=1)
        h(tx=b'\x30\x00')
        assert h._last_tx == b'\x30\x00'

    def test_last_tx_not_set_for_rx_only(self):
        h = _make_handler()
        h(rx=b'\x0A')
        assert h._last_tx is None


class TestBitInfo:

    def test_tx_bits_7_shows_in_output(self):
        h = _make_handler(parse_level=0)
        h(tx=b'\x26', tx_bits=7)
        msg = h.logger_func.call_args[0][0]
        assert "[7 bits]" in msg
        assert "26" in msg

    def test_rx_bits_4_shows_in_output(self):
        h = _make_handler(parse_level=0)
        h(rx=b'\x04', rx_bits=4)
        msg = h.logger_func.call_args[0][0]
        assert "[4 bits]" in msg

    def test_full_byte_no_bits_annotation(self):
        h = _make_handler(parse_level=0)
        h(tx=b'\x30\x04')
        msg = h.logger_func.call_args[0][0]
        assert "bits" not in msg

    def test_bits_8_treated_as_full_byte(self):
        h = _make_handler(parse_level=0)
        h(tx=b'\x30\x04', tx_bits=8)
        msg = h.logger_func.call_args[0][0]
        assert "bits" not in msg

    def test_tx_bits_with_summary_parser(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=1)
        h(tx=b'\x26', tx_bits=7)
        msg = h.logger_func.call_args[0][0]
        assert "[7 bits]" in msg

    def test_rx_bits_with_summary_parser(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=1)
        h(tx=b'\x30\x00')
        h(rx=b'\x04', rx_bits=4)
        rx_msg = h.logger_func.call_args_list[1][0][0]
        assert "[4 bits]" in rx_msg

    def test_bits_0_no_annotation(self):
        h = _make_handler(parse_level=0)
        h(tx=b'\x26', tx_bits=0)
        msg = h.logger_func.call_args[0][0]
        assert "bits" not in msg

    def test_last_tx_bits_recorded(self):
        h = _make_handler(parse_level=0)
        h(tx=b'\x26', tx_bits=7)
        assert h._last_tx_bits == 7


class TestFlushFalse:

    def test_tx_flush_false_buffers(self):
        h = _make_handler(parse_level=0)
        h(tx=b'\x30\x04', flush=False)
        h.logger_func.assert_not_called()
        h(tx=b'\x00\x01')
        h.logger_func.assert_called_once()
        msg = h.logger_func.call_args[0][0]
        assert "30 04 00 01" in msg

    def test_rx_flush_false_buffers(self):
        h = _make_handler(parse_level=0)
        h(rx=b'\xAA\xBB', flush=False)
        h.logger_func.assert_not_called()
        h(rx=b'\xCC')
        h.logger_func.assert_called_once()
        msg = h.logger_func.call_args[0][0]
        assert "AA BB CC" in msg


class TestSummaryNone:

    def test_tx_summary_none_falls_back_to_raw(self):
        from unittest.mock import MagicMock
        class NoSummaryParser:
            def can_parse(self, data):
                return True
            def summary(self, data):
                return None
        h = _make_handler(parsers=[NoSummaryParser()], parse_level=1)
        h(tx=b'\x30\x04')
        msg = h.logger_func.call_args[0][0]
        assert "30 04" in msg


class TestParseLevel2:

    def test_rx_parse_level_2_returns_raw_with_frame(self):
        from nfctester.parsers import T2TParser
        h = _make_handler(parsers=[T2TParser()], parse_level=2)
        h(tx=b'\x30\x00')
        h(rx=b'\x01\x02\x03\x04')
        msg = h.logger_func.call_args_list[1][0][0]
        assert "01 02 03 04" in msg
