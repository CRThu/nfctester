import pytest
from nfctester.cards import NTAG21x
from nfctester.trace import trace

@pytest.fixture
def ntag(card_reader):
    """获取 NTAG21x 实例的 fixture"""
    card_info = card_reader.active()
    assert card_info is not None, "未找到卡片，请确保 NTAG21x 标签已放置在读卡器上"
    return NTAG21x(card_reader)

@pytest.mark.hil
@pytest.mark.ntag21x
def test_ntag_get_version(ntag):
    """
    测试获取 NTAG21x 版本信息
    预期响应为 8 字节，包含厂商、产品类型、容量等信息
    """
    version = ntag.get_version()
    
    assert len(version) == 8
    assert version[0] == 0x00
    assert version[2] == 0x04
    assert version[7] == 0x03
    
    trace.info(f"[GET_VERSION]: {version.hex().upper()}")


@pytest.mark.hil
@pytest.mark.ntag21x
def test_ntag_auth_and_protection(ntag):
    """
    测试 NTAG21x 认证及页面保护逻辑
    1. 备份关键页
    2. 设置认证起始页为 0x04 (保护用户数据区)
    3. 恢复现场 (恢复无保护状态)
    """
    # 自动识别卡片型号以确定配置页地址
    version = ntag.get_version()
    assert len(version) == 8
    
    # NTAG213: 0x29, NTAG215: 0x83, NTAG216: 0xE3
    # 这里通过 Page 3 (CC) 的容量字节简单判断
    cc = ntag.read_page(3)
    capacity = cc[2] * 8
    
    if capacity <= 144:  # NTAG213
        cfg_base = 0x29
    elif capacity <= 496:  # NTAG215
        cfg_base = 0x83
    else:  # NTAG216
        cfg_base = 0xE3
        
    auth0_addr = cfg_base
    pwd_addr = cfg_base + 2
    pack_addr = cfg_base + 3
    
    # 设置密码和保护范围
    test_pwd = b'\x12\x34\x56\x78'
    # pack = ntag.auth(test_pwd)
    try:
        # 写入新密码
        ntag.write_page(pwd_addr, test_pwd)

        # 设置 AUTH0 = 0x04 (从第 4 页开始受保护)
        # MIRROR(0x04) RFUI(0x00) MIRROR_PAGE(0x00) AUTH0(0xFF->0x04)
        ntag.write_page(auth0_addr, b'\x04\x00\x00\x04')
        # ntag.write_page(auth0_addr, b'\x04\x00\x00\xFF') 
        
        data = ntag.read_page(0x04)
        assert data is not None
        
    finally:
        # 恢复现场
        try:
            ntag.auth(test_pwd)
            # 恢复 AUTH0 = 0xFF (关闭保护)
            ntag.write_page(auth0_addr, b'\x04\x00\x00\xFF')
            # 恢复默认密码
            ntag.write_page(pwd_addr, b'\xFF\xFF\xFF\xFF')
        except Exception as e:
            trace.error(f"Failed to restore tag state: {e}")
