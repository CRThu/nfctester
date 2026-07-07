"""TraceManager 测试: set_level, set_layer, set_parse, add_sink/remove_sink, _filter"""
from unittest.mock import MagicMock, patch
from nfctester.trace.manager import TraceManager


def _make_manager(**env_overrides):
    with patch.dict("os.environ", env_overrides):
        return TraceManager()


class TestSetLevel:

    def test_set_level_updates_min_level(self):
        m = _make_manager()
        m.set_level("DEBUG")
        assert m._min_level == "DEBUG"

    def test_set_level_is_case_insensitive(self):
        m = _make_manager()
        m.set_level("error")
        assert m._min_level == "ERROR"


class TestSetLayer:

    def test_set_layer_enable(self):
        m = _make_manager()
        m.set_layer("DRIVER", enable=True)
        assert m.driver.enabled is True

    def test_set_layer_disable(self):
        m = _make_manager(CRFT_TRACE_DRIVER="1")
        m.set_layer("DRIVER", enable=False)
        assert m.driver.enabled is False

    def test_set_layer_unknown_name_ignored(self):
        m = _make_manager()
        m.set_layer("UNKNOWN", enable=True)


class TestSetParse:

    def test_set_parse_updates_all_handlers(self):
        m = _make_manager()
        m.set_parse(level=0)
        assert m.driver.parse_level == 0
        assert m.protocol.parse_level == 0

    def test_set_parse_default(self):
        m = _make_manager(CRFT_TRACE_PARSE="0")
        m.set_parse(level=1)
        assert m.driver.parse_level == 1


class TestAddRemoveSink:

    def test_add_sink_to_all_handlers(self):
        m = _make_manager()
        fn = MagicMock()
        m.add_sink(fn)
        assert fn in m.driver._sinks
        assert fn in m.protocol._sinks

    def test_remove_sink_from_all_handlers(self):
        m = _make_manager()
        fn = MagicMock()
        m.add_sink(fn)
        m.remove_sink(fn)
        assert fn not in m.driver._sinks
        assert fn not in m.protocol._sinks

    def test_add_sink_no_duplicate(self):
        m = _make_manager()
        fn = MagicMock()
        m.add_sink(fn)
        m.add_sink(fn)
        assert m.driver._sinks.count(fn) == 1


class TestFilter:

    def test_filter_known_layer_returns_enabled(self):
        m = _make_manager()
        m.driver.enabled = True
        record = {"extra": {"layer": "DRIVER"}, "level": MagicMock(no=20)}
        assert m._filter(record) is True

    def test_filter_known_layer_disabled(self):
        m = _make_manager()
        m.driver.enabled = False
        record = {"extra": {"layer": "DRIVER"}, "level": MagicMock(no=20)}
        assert m._filter(record) is False

    def test_filter_unknown_layer_uses_level(self):
        m = _make_manager()
        record = {"extra": {"layer": "APP"}, "level": MagicMock(no=10)}
        assert m._filter(record) is False

    def test_filter_unknown_layer_no_extra(self):
        m = _make_manager()
        record = {"extra": {}, "level": MagicMock(no=20)}
        assert m._filter(record) is True


class TestSetParser:

    def test_set_parser_updates_protocol(self):
        m = _make_manager()
        m.set_parser(atqa=0x0044, sak=0x00)
        assert len(m.protocol.parsers) == 1

    def test_set_parser_no_match_keeps_existing(self):
        m = _make_manager()
        original_parsers = m.protocol.parsers[:]
        m.set_parser(atqa=0xFFFF, sak=0xFF)
        assert m.protocol.parsers == original_parsers


class TestGetParseLevel:

    def test_parse_level_off(self):
        m = _make_manager(CRFT_TRACE_PARSE="off")
        assert m.driver.parse_level == 0

    def test_parse_level_on(self):
        m = _make_manager(CRFT_TRACE_PARSE="1")
        assert m.driver.parse_level == 1


class TestGetEnvBool:

    def test_bool_true_values(self):
        m = _make_manager()
        for val in ("1", "true", "yes", "on", "True", "YES"):
            assert m._get_env_bool("TEST_KEY", False) is False
            with patch.dict("os.environ", {"TEST_KEY": val}):
                assert m._get_env_bool("TEST_KEY", False) is True

    def test_bool_false_values(self):
        m = _make_manager()
        for val in ("0", "false", "no", "off"):
            with patch.dict("os.environ", {"TEST_KEY": val}):
                assert m._get_env_bool("TEST_KEY", True) is False
