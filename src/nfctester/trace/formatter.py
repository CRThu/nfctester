from nfctester.parsers import ParsedFrame

import os

# 简单解析模式下 hex 列的对齐宽度
_HEX_COL_WIDTH = int(os.getenv("NFC_TRACE_HEX_WIDTH", "48"))


class TraceFormatter:
    """将 trace 数据渲染为对齐文本"""

    @staticmethod
    def format_raw(direction: str, raw: bytes, bits: int = 0) -> str:
        """无法解析时的降级输出（仅显示原始 hex）"""
        arrow = "->" if direction == "TX" else "<-"
        hex_str = raw.hex(' ').upper()
        if bits not in (0, 8):
            return f"{direction} {arrow}  {hex_str} [{bits} bits]"
        return f"{direction} {arrow}  {hex_str}"

    @staticmethod
    def format_summary(direction: str, raw: bytes, summary: str, bits: int = 0) -> str:
        """简单解析模式：原始 hex + 一行摘要，括号对齐"""
        arrow = "->" if direction == "TX" else "<-"
        hex_str = raw.hex(' ').upper()
        bit_tag = f" [{bits} bits]" if bits not in (0, 8) else ""
        return f"{direction} {arrow}  {hex_str:<{_HEX_COL_WIDTH}} [{summary}{bit_tag}]"

    @staticmethod
    def format_encrypted_pair(direction: str, raw: bytes, plaintext: bytes, bits: int = 0) -> str:
        """加密双行输出: [encrypted] hex + [decrypted] plaintext"""
        arrow = "->" if direction == "TX" else "<-"
        enc_hex = raw.hex(' ').upper()
        dec_hex = plaintext.hex(' ').upper()
        w = _HEX_COL_WIDTH
        return (
            f"{direction} {arrow}  {enc_hex:<{w}} [encrypted]\n"
            f"{' ' * len(direction)} {' ' * len(arrow)}  {dec_hex:<{w}} [decrypted]"
        )
