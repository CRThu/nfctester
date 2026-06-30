import pytest
from nfctester.cards import MifareClassicCard

@pytest.fixture
def card(card_reader):
    """获取 MifareClassicCard 实例的 fixture"""
    card_info = card_reader.active()
    assert card_info is not None, "未找到卡片"
    return MifareClassicCard(card_reader)

def create_value_block(value: int, addr: int) -> bytes:
    """创建 Mifare Classic 数值块格式"""
    v_bytes = value.to_bytes(4, 'little')
    v_inv_bytes = bytes([b ^ 0xFF for b in v_bytes])
    a_byte = addr & 0xFF
    a_inv_byte = (addr ^ 0xFF) & 0xFF
    return v_bytes + v_inv_bytes + v_bytes + bytes([a_byte, a_inv_byte, a_byte, a_inv_byte])

@pytest.mark.mifare
@pytest.mark.dependency(name="mifare_auth")
def test_mifare_auth(card):
    """测试 MIFARE Classic 认证：KeyA 和 KeyB"""
    default_key = b'\xFF' * 6
    # 测试第 1 扇区的第 4 块
    assert card.authenticate(0x04, default_key, key_type=0x60) is True
    assert card.authenticate(0x04, default_key, key_type=0x61) is True

@pytest.mark.mifare
@pytest.mark.dependency(depends=["mifare_auth"])
def test_mifare_read_write(card):
    """测试 MIFARE Classic 块读写"""
    default_key = b'\xFF' * 6
    block_addr = 0x04

    assert card.authenticate(block_addr, default_key) is True

    # 读取原始数据
    original_data = card.read_block(block_addr)
    assert len(original_data) == 16

    # 写入并验证
    test_data = bytes([i for i in range(16)])
    assert card.write_block(block_addr, test_data) is True
    assert card.read_block(block_addr) == test_data

    # 恢复原始数据
    assert card.write_block(block_addr, original_data) is True

@pytest.mark.mifare
@pytest.mark.dependency(name="mifare_value_init", depends=["mifare_auth"])
def test_mifare_value_init(card):
    """测试 MIFARE Classic 数值块初始化"""
    default_key = b'\xFF' * 6
    block_addr = 0x05

    assert card.authenticate(block_addr, default_key) is True

    initial_val = 1000
    vb = create_value_block(initial_val, block_addr)
    assert card.write_block(block_addr, vb) is True

@pytest.mark.mifare
@pytest.mark.dependency(depends=["mifare_value_init"])
def test_mifare_value_ops(card):
    """测试 MIFARE Classic 数值块操作：Increment, Decrement, Restore, Transfer"""
    default_key = b'\xFF' * 6
    block_addr = 0x05

    assert card.authenticate(block_addr, default_key) is True

    # 1. 测试 Increment (1000 + 500 = 1500)
    assert card.increment_block(block_addr, 500) is True
    assert card.transfer_block(block_addr) is True
    res = card.read_block(block_addr)
    assert int.from_bytes(res[0:4], 'little') == 1500

    # 2. 测试 Decrement (1500 - 200 = 1300)
    assert card.decrement_block(block_addr, 200) is True
    assert card.transfer_block(block_addr) is True
    res = card.read_block(block_addr)
    assert int.from_bytes(res[0:4], 'little') == 1300

    # 3. 测试 Restore
    assert card.restore_block(block_addr) is True
    assert card.transfer_block(block_addr) is True
    res = card.read_block(block_addr)
    assert int.from_bytes(res[0:4], 'little') == 1300
