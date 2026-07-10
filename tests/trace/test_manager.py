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
        assert m._min_level_name == "DEBUG"

    def test_set_level_is_case_insensitive(self):
        m = _make_manager()
        m.set_level("error")
        assert m._min_level_name == "ERROR"


class TestSetLayer:

    def test_set_layer_enable(self):
        m = _make_manager()
        m.set_layer("driver", enable=True)
        assert m._layer_on["driver"] is True

    def test_set_layer_disable(self):
        m = _make_manager(NFC_TRACE="driver")
        m.set_layer("driver", enable=False)
        assert m._layer_on["driver"] is False

    def test_set_layer_unknown_name_ignored(self):
        m = _make_manager()
        m.set_layer("UNKNOWN", enable=True)


class TestSetParse:

    def test_set_parse_updates_all_handlers(self):
        m = _make_manager()
        m.set_parse(level=0)
        assert m._layers["driver"].parse_level == 0
        assert m._layers["protocol"].parse_level == 0

    def test_set_parse_default(self):
        m = _make_manager()
        m.set_parse(level=1)
        assert m._layers["driver"].parse_level == 1


class TestAddRemoveSink:

    def test_add_sink_to_all_handlers(self):
        m = _make_manager()
        fn = MagicMock()
        m.add_sink(fn)
        assert fn in m._layers["driver"]._sinks
        assert fn in m._layers["protocol"]._sinks

    def test_remove_sink_from_all_handlers(self):
        m = _make_manager()
        fn = MagicMock()
        m.add_sink(fn)
        m.remove_sink(fn)
        assert fn not in m._layers["driver"]._sinks
        assert fn not in m._layers["protocol"]._sinks

    def test_add_sink_no_duplicate(self):
        m = _make_manager()
        fn = MagicMock()
        m.add_sink(fn)
        m.add_sink(fn)
        assert m._layers["driver"]._sinks.count(fn) == 1


class TestFilter:

    def test_filter_known_layer_returns_enabled(self):
        m = _make_manager()
        m._layer_on["app"] = True
        record = {"extra": {"layer": "app"}, "level": MagicMock(no=50)}
        assert m._filter(record) is True

    def test_filter_known_layer_disabled(self):
        m = _make_manager()
        m._layer_on["app"] = False
        record = {"extra": {"layer": "app"}, "level": MagicMock(no=50)}
        assert m._filter(record) is False

    def test_filter_layer_below_min_level(self):
        """Layer ON but layer level < min_level → filtered out"""
        m = _make_manager()
        m._layer_on["driver"] = True
        m._min_level_name = "WARNING"
        record = {"extra": {"layer": "driver"}, "level": MagicMock(no=5)}
        assert m._filter(record) is False

    def test_filter_unknown_layer_uses_level(self):
        m = _make_manager()
        record = {"extra": {"layer": "unknown"}, "level": MagicMock(no=10)}
        assert m._filter(record) is False

    def test_filter_no_layer_above_min_level(self):
        m = _make_manager()
        record = {"extra": {}, "level": MagicMock(no=40)}
        assert m._filter(record) is True

    def test_filter_no_layer_below_min_level(self):
        m = _make_manager()
        record = {"extra": {}, "level": MagicMock(no=20)}
        assert m._filter(record) is False


class TestSetParser:

    def test_set_parser_updates_protocol(self):
        m = _make_manager()
        m.set_parser(atqa=0x0044, sak=0x00)
        assert len(m._layers["protocol"].parsers) == 1

    def test_set_parser_no_match_keeps_existing(self):
        m = _make_manager()
        original_parsers = m._layers["protocol"].parsers[:]
        m.set_parser(atqa=0xFFFF, sak=0xFF)
        assert m._layers["protocol"].parsers == original_parsers


class TestPropertyControl:

    def test_getattr_layer(self):
        m = _make_manager()
        assert m.driver is False
        assert m.protocol is False

    def test_setattr_layer(self):
        m = _make_manager()
        m.driver = True
        assert m._layer_on["driver"] is True

    def test_setattr_level(self):
        m = _make_manager()
        m.level = "error"
        assert m._min_level_name == "ERROR"


class TestDefaultStates:

    def test_app_on_by_default(self):
        m = _make_manager()
        assert m._layer_on["app"] is True

    def test_warning_on_by_default(self):
        m = _make_manager()
        assert m._layer_on["warning"] is True

    def test_error_on_by_default(self):
        m = _make_manager()
        assert m._layer_on["error"] is True

    def test_driver_off_by_default(self):
        m = _make_manager()
        assert m._layer_on["driver"] is False

    def test_debug_off_by_default(self):
        m = _make_manager()
        assert m._layer_on["debug"] is False

    def test_protocol_off_by_default(self):
        m = _make_manager()
        assert m._layer_on["protocol"] is False

    def test_min_level_is_warning(self):
        m = _make_manager()
        assert m._min_level_name == "WARNING"


class TestEnvVarParsing:

    def test_nfc_trace_enables_layers(self):
        m = _make_manager(NFC_TRACE="driver,protocol")
        assert m._layer_on["driver"] is True
        assert m._layer_on["protocol"] is True

    def test_nfc_trace_all(self):
        m = _make_manager(NFC_TRACE="all")
        for name in ["driver", "debug", "protocol", "warning", "error", "app"]:
            assert m._layer_on[name] is True

    def test_nfc_trace_level(self):
        m = _make_manager(NFC_TRACE_LEVEL="debug")
        assert m._min_level_name == "DEBUG"


class TestFilterIntersection:

    def test_protocol_on_level_trace_passes(self):
        """Protocol layer (15) >= trace level (5) → should pass"""
        m = _make_manager()
        m._layer_on["protocol"] = True
        m._min_level_name = "TRACE"
        record = {"extra": {"layer": "protocol"}, "level": MagicMock(no=15)}
        assert m._filter(record) is True

    def test_protocol_on_level_warning_filters(self):
        """Protocol layer (15) < warning level (30) → should be filtered"""
        m = _make_manager()
        m._layer_on["protocol"] = True
        m._min_level_name = "WARNING"
        record = {"extra": {"layer": "protocol"}, "level": MagicMock(no=15)}
        assert m._filter(record) is False

    def test_driver_on_level_trace_passes(self):
        """Driver layer (5) >= trace level (5) → should pass"""
        m = _make_manager()
        m._layer_on["driver"] = True
        m._min_level_name = "TRACE"
        record = {"extra": {"layer": "driver"}, "level": MagicMock(no=5)}
        assert m._filter(record) is True

    def test_app_always_passes_when_on(self):
        """App layer (50) >= any level → should always pass when ON"""
        m = _make_manager()
        m._layer_on["app"] = True
        m._min_level_name = "WARNING"
        record = {"extra": {"layer": "app"}, "level": MagicMock(no=50)}
        assert m._filter(record) is True

    def test_error_passes_when_on(self):
        m = _make_manager()
        m._layer_on["error"] = True
        m._min_level_name = "ERROR"
        record = {"extra": {"layer": "error"}, "level": MagicMock(no=40)}
        assert m._filter(record) is True


class TestLogMethod:

    def test_log_dispatches_to_text_logger(self):
        m = _make_manager()
        m.log("test message", layer="app")
        # app layer uses logger.success, which goes through loguru

    def test_log_unknown_layer_falls_back_to_info(self):
        m = _make_manager()
        m.log("fallback", layer="unknown")


class TestConvenienceMethods:
    """测试简洁方法: app(), debug(), warning(), error()"""

    def test_app_method(self):
        m = _make_manager()
        m.app("app message")

    def test_debug_method(self):
        m = _make_manager()
        m.debug("debug message")

    def test_warning_method(self):
        m = _make_manager()
        m.warning("warning message")

    def test_error_method(self):
        m = _make_manager()
        m.error("error message")


class TestLevelProperty:
    """测试 level 属性控制"""

    def test_getattr_level_returns_string(self):
        m = _make_manager()
        assert m.level == "warning"

    def test_setattr_level_with_string(self):
        m = _make_manager()
        m.level = "error"
        assert m._min_level_name == "ERROR"

    def test_setattr_level_with_int(self):
        m = _make_manager()
        m.level = 40
        assert m._min_level_name == "ERROR"

    def test_setattr_level_case_insensitive(self):
        m = _make_manager()
        m.level = "DEBUG"
        assert m._min_level_name == "DEBUG"
