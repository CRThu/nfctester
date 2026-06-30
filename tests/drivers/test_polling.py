import pytest
from loguru import logger

@pytest.mark.hil
def test_poll_card(card_reader):
    """测试寻卡功能"""
    card_info = card_reader.active()
    
    assert card_info is not None, "未发现卡片"
    
    sak = card_info.sak
    uid = card_info.uid
    
    card_type = "未知类型"
    if sak == 0x00:
        card_type = "NTAG / Mifare Ultralight"
    elif sak == 0x08:
        card_type = "Mifare Classic 1K"
    elif sak == 0x18:
        card_type = "Mifare Classic 4K"
    elif sak == 0x20:
        card_type = "ISO14443-4 兼容卡"

    logger.success(f"发现卡片! 类型: {card_type}")
    logger.info(f"UID: {uid.hex(' ').upper()} | SAK: 0x{sak:02X}")
