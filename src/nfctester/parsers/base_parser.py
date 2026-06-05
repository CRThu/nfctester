from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ParsedField:
    """单个解析字段"""
    name: str           # 字段名，如 "FRAME HEADER"
    raw: bytes          # 字段原始字节
    value: int          # 字段数值（多字节时取首字节或组合值）
    description: str    # 描述，如 "Valid" / "19 bytes"
    children: List["ParsedField"] = field(default_factory=list)  # 子字段

    @property
    def hex_str(self) -> str:
        """以空格分隔的大写十六进制字符串"""
        return self.raw.hex(" ").upper()


@dataclass
class ParsedFrame:
    """解析结果，包含顶层字段列表"""
    raw: bytes
    label: str                          # 帧类型标签，如 "PN532 Normal Frame"
    fields: List[ParsedField] = field(default_factory=list)
    is_valid: bool = True               # 解析是否成功

    @property
    def raw_hex(self) -> str:
        return self.raw.hex(" ").upper()


class BaseParser(ABC):
    """解析器抽象基类，子类实现具体协议的字段解析"""

    @abstractmethod
    def can_parse(self, data: bytes) -> bool:
        """判断该解析器是否能处理此数据"""
        ...

    @abstractmethod
    def parse(self, data: bytes) -> ParsedFrame:
        """解析字节流，返回 ParsedFrame"""
        ...
