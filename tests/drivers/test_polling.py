import pytest
from loguru import logger
from nfctester.parsers.registry import ParserRegistry


@pytest.mark.hil
def test_poll_card(card_reader):
    """测试寻卡功能"""
    card_info = card_reader.active()

    assert card_info is not None, "未发现卡片"

    sak = card_info.sak
    uid = card_info.uid
    atqa = int.from_bytes(card_info.atq, "little")

    name = ParserRegistry.get_name(atqa, sak) or "未知类型"
    logger.success(f"发现卡片! 类型: {name}")
    logger.info(f"UID: {' '.join(f'{b:02X}' for b in uid)} | SAK: 0x{sak:02X}")
