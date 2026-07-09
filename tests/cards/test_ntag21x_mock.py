import pytest
from nfctester.cards import NTAG21x
from nfctester.drivers.card_reader import TransceiveBits


@pytest.fixture
def ntag(mock_reader):
    return NTAG21x(mock_reader)


def test_ntag_get_version(mock_reader, ntag):
    """验证 get_version 发送 0x60 指令并返回 8 字节版本"""
    version_data = [0x00, 0x04, 0x04, 0x02, 0x01, 0x00, 0x11, 0x03]
    mock_reader.transceive.return_value = TransceiveBits(data=version_data, bits=0)

    result = ntag.get_version()

    assert result == version_data
    assert len(result) == 8
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd == [0x60]


def test_ntag_auth_success(mock_reader, ntag):
    """验证 PwdAuth 命令格式和 PACK 响应"""
    password = [0x12, 0x34, 0x56, 0x78]
    pack = [0xAB, 0xCD]
    mock_reader.transceive.return_value = TransceiveBits(data=pack, bits=0)

    result = ntag.auth(password)

    assert result == pack
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd == [0x1B] + password


def test_ntag_auth_invalid_password_length(ntag):
    """验证密码长度校验"""
    with pytest.raises(ValueError):
        ntag.auth([0x12, 0x34])


def test_ntag_auth_no_response(mock_reader, ntag):
    """验证认证失败（NAK）时抛出 PermissionError"""
    mock_reader.transceive.return_value = TransceiveBits(data=[], bits=0)

    with pytest.raises(PermissionError):
        ntag.auth([0x12, 0x34, 0x56, 0x78])


def test_ntag_auth_unexpected_response(mock_reader, ntag):
    """验证非预期响应长度时抛出 PermissionError"""
    mock_reader.transceive.return_value = TransceiveBits(data=[0x00, 0x00, 0x00], bits=0)

    with pytest.raises(PermissionError):
        ntag.auth([0x12, 0x34, 0x56, 0x78])


def test_ntag_read_page(mock_reader, ntag):
    """验证 read_page 继承自 Type2Tag 的 READ 命令"""
    page_data = list(range(16))
    mock_reader.transceive.return_value = TransceiveBits(data=page_data, bits=0)

    result = ntag.read_page(0x04)

    assert result == page_data
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd == [0x30, 0x04]
