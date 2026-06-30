import pytest
from nfctester.cards import Type2Tag

@pytest.fixture
def t2t_card(card_reader):
    """获取 Type2Tag 实例的 fixture"""
    card_info = card_reader.active()
    assert card_info is not None, "未找到卡片，请确保 NFC 标签已放置在读卡器上"
    return Type2Tag(card_reader)

@pytest.mark.hil
@pytest.mark.t2t
def test_t2t_read_write_tag(t2t_card):
    """测试 Type 2 Tag 基础读写流程"""
    # 用户数据区通常从 0x04 页开始
    page_addr = 0x04
    
    # 1. 读取原始数据 (T2T READ 返回 16 字节，包含从指定页开始的 4 个页)
    original_data_full = t2t_card.read_page(page_addr)
    assert original_data_full is not None
    assert len(original_data_full) == 16
    original_data = original_data_full[0:4]

    # 2. 写入测试数据 (必须为 4 字节)
    test_data = b'\xDE\xAD\xBE\xEF'
    t2t_card.write_page(page_addr, test_data)
    
    # 3. 验证写入结果
    updated_data_full = t2t_card.read_page(page_addr)
    assert updated_data_full[0:4] == test_data
    
    # 4. 恢复原始数据 (清理测试痕迹)
    t2t_card.write_page(page_addr, original_data)
    assert t2t_card.read_page(page_addr)[0:4] == original_data


@pytest.mark.hil
@pytest.mark.t2t
def test_t2t_ndef_operations(t2t_card):
    """
    测试 NDEF 写入与读取
    """
    # 写入一个简单的 NDEF 结构
    # T=0x03, L=0x04, V=[0xAA, 0xBB, 0xCC, 0xDD], Terminator=0xFE
    p4 = b'\x03\x04\xAA\xBB'
    p5 = b'\xCC\xDD\xFE\x00'
    
    # 备份 Page 4, 5
    p4_backup = t2t_card.read_page(4)[0:4]
    p5_backup = t2t_card.read_page(5)[0:4]
    
    try:
        t2t_card.write_page(4, p4)
        t2t_card.write_page(5, p5)
        
        # 使用 read_ndef 读取并验证
        res = t2t_card.read_ndef()
        assert res["ndef"] == b'\xAA\xBB\xCC\xDD'
        
    finally:
        # 恢复
        t2t_card.write_page(4, p4_backup)
        t2t_card.write_page(5, p5_backup)
