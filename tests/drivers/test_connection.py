import pytest

@pytest.mark.hil
def test_firmware_version(card_reader):
    """测试读取固件版本"""
    version = card_reader.get_version()
    assert version is not None, "无法读取固件版本"
    print(f"固件版本: {version}")