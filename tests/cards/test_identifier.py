"""解析器注册模块单元测试"""
import pytest
from nfctester.parsers.registry import ParserRegistry


class TestParserRegistry:
    def test_mifare_classic_registered(self):
        from nfctester.parsers.mifare_classic_parser import MifareClassicParser
        cls = ParserRegistry.get(0x0004, 0x08)
        assert cls is MifareClassicParser

    def test_mifare_classic_4k(self):
        from nfctester.parsers.mifare_classic_parser import MifareClassicParser
        cls = ParserRegistry.get(0x0002, 0x18)
        assert cls is MifareClassicParser

    def test_type2tag_registered(self):
        from nfctester.parsers.t2t_parser import T2TParser
        cls = ParserRegistry.get(0x0044, 0x00)
        assert cls is T2TParser

    def test_mifare_classic_7byte_uid(self):
        from nfctester.parsers.mifare_classic_parser import MifareClassicParser
        cls = ParserRegistry.get(0x0044, 0x08)
        assert cls is MifareClassicParser

    def test_no_match(self):
        cls = ParserRegistry.get(0xFFFF, 0xFF)
        assert cls is None

    def test_get_name(self):
        name = ParserRegistry.get_name(0x0004, 0x08)
        assert name == "MIFARE Classic 1K"

    def test_get_name_no_match(self):
        name = ParserRegistry.get_name(0xFFFF, 0xFF)
        assert name is None

    def test_list(self):
        keys = ParserRegistry.list()
        assert (0x0004, 0x08) in keys
        assert (0x0044, 0x00) in keys

    def test_register_decorator(self):
        from nfctester.parsers.base_parser import BaseParser

        class DummyParser(BaseParser):
            def can_parse(self, data): return False
            def parse(self, data): return None

        @ParserRegistry.register(atqa=0xDEAD, sak=0xBE, name="Dummy")
        class _DummyParser(DummyParser): ...

        cls = ParserRegistry.get(0xDEAD, 0xBE)
        assert cls is _DummyParser
        assert ParserRegistry.get_name(0xDEAD, 0xBE) == "Dummy"

        ParserRegistry._parsers.pop((0xDEAD, 0xBE))
        ParserRegistry._names.pop((0xDEAD, 0xBE))
