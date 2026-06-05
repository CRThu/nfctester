from nfctester.parsers import ParsedFrame, ParsedField

# 分隔线长度
_SEP_LEN = 55
_SEP = "-" * _SEP_LEN

# 顶层字段用 [+] 展开（含子字段），[-] 展开（仅描述）
_ICON_HAS_CHILDREN = "[+]"
_ICON_LEAF         = "[-]"
_CHILD_PREFIX      = "    |-- "
_CHILD_PAD         = "    "


def _field_header_line(icon: str, name: str, raw_hex: str, description: str, col: int = 18) -> str:
    """
    生成顶层字段行，格式：
      [+]- FRAME HEADER      : 00 00 FF
    或包含描述时：
      [-]- APPLICATION LAYER : D5 43 00 ...
    """
    # 字段名对齐
    padded_name = f"{name:<{col}}"
    return f"{icon}- {padded_name}: {raw_hex}"


def _child_line(name: str, value_hex: str, description: str, col: int = 14) -> str:
    """
    生成子字段行，格式：
      |-- Length         : 0x13 (19 bytes)
    """
    padded_name = f"{name:<{col}}"
    return f"{_CHILD_PREFIX}{padded_name}: {value_hex}  ({description})"


class TraceFormatter:
    """
    将 ParsedFrame 渲染成对齐的树状文本。

    输出格式示例：
      00 00 FF 13 ED D5 43 00 ...

      -------------------------------------------------------

      [+]- FRAME HEADER      : 00 00 FF
      [+]- FRAME CONTROL     : 13 ED
          |-- Length         : 0x13  (19 bytes)
          |-- Length Check   : 0xED  (Valid)
      [-]- APPLICATION LAYER : D5 43 00 ...
          |-- Direction      : 0xD5  (Device to Host)
          |-- Command        : 0x43  (InCommunicateThru Response)
          |-- Status         : 0x00  (Success)
          |-- Payload Data   : DE AD BE EF ...
    """

    @staticmethod
    def format(direction: str, frame: ParsedFrame) -> str:
        """
        渲染输出字符串。

        :param direction: "TX" 或 "RX"
        :param frame:     ParsedFrame 解析结果
        """
        arrow = "->" if direction == "TX" else "<-"
        lines = []

        # 第一行：原始 hex 总览
        lines.append(f"{direction} {arrow}  {frame.raw_hex}")
        lines.append(_SEP)

        # 遍历顶层字段
        for f in frame.fields:
            has_children = bool(f.children)
            icon = _ICON_HAS_CHILDREN if has_children else _ICON_LEAF
            lines.append(_field_header_line(icon, f.name, f.hex_str, f.description))

            # 子字段
            for child in f.children:
                # 值显示：多字节用 hex_str，单字节用 0xNN
                if len(child.raw) == 1:
                    val_str = f"0x{child.value:02X}"
                else:
                    val_str = child.hex_str
                lines.append(_child_line(child.name, val_str, child.description))

        lines.append("")  # 末尾空行
        return "\n".join(lines)

    @staticmethod
    def format_raw(direction: str, raw: bytes) -> str:
        """无法解析时的降级输出（仅显示原始 hex）"""
        arrow = "->" if direction == "TX" else "<-"
        return f"{direction} {arrow}  {raw.hex(' ').upper()}"
