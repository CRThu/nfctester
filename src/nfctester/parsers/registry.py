from __future__ import annotations
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_parser import BaseParser


class ParserRegistry:
    """协议解析器注册表，通过 ATQA/SAK 映射到对应解析器类。

    用法:
        @ParserRegistry.register(atqa=0x0004, sak=0x08, name="MIFARE Classic 1K")
        class MifareClassicParser(BaseParser): ...

        parser_cls = ParserRegistry.get(atqa=0x0004, sak=0x08)
        name = ParserRegistry.get_name(atqa=0x0004, sak=0x08)
    """

    _parsers: dict[tuple[int, int], type[BaseParser]] = {}
    _names: dict[tuple[int, int], str] = {}

    @classmethod
    def register(cls, atqa: int, sak: int, name: str):
        """装饰器，注册解析器类到 ATQA/SAK 映射。

        Args:
            atqa: Answer To Request A 的 2 字节值 (little-endian)。
            sak: Select Acknowledge 的 1 字节值。
            name: 卡片类型显示名称。
        """
        def decorator(parser_cls: type[BaseParser]) -> type[BaseParser]:
            key = (atqa, sak)
            cls._parsers[key] = parser_cls
            cls._names[key] = name
            return parser_cls
        return decorator

    @classmethod
    def get(cls, atqa: int, sak: int) -> type[BaseParser] | None:
        """根据 ATQA/SAK 返回匹配的解析器类，无匹配返回 None。"""
        return cls._parsers.get((atqa, sak))

    @classmethod
    def get_name(cls, atqa: int, sak: int) -> str | None:
        """根据 ATQA/SAK 返回卡片类型名称，无匹配返回 None。"""
        return cls._names.get((atqa, sak))

    @classmethod
    def list(cls) -> list[tuple[int, int]]:
        """返回所有已注册的 ATQA/SAK 键列表。"""
        return list(cls._parsers.keys())
