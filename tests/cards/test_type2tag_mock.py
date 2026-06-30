import pytest
from nfctester.cards import Type2Tag
from nfctester.drivers.card_reader import TransceiveResult


@pytest.fixture
def tag(mock_reader):
    return Type2Tag(mock_reader)


def test_t2t_read_page(mock_reader, tag):
    """验证 read_page 生成的 READ 命令"""
    page_data = bytes(range(16))
    mock_reader.transceive.return_value = TransceiveResult(data=page_data, rx_bits=0)

    result = tag.read_page(0x04)

    assert result == page_data
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd == bytes([0x30, 0x04])


def test_t2t_read_page_no_response(mock_reader, tag):
    """验证 read_page 在无响应时抛出异常"""
    mock_reader.transceive.return_value = TransceiveResult(data=None, rx_bits=0)

    with pytest.raises(RuntimeError):
        tag.read_page(0x04)


def test_t2t_write_page(mock_reader, tag):
    """验证 write_page 生成的 WRITE 命令和参数"""
    mock_reader.transceive.return_value = TransceiveResult(data=b'\x0A', rx_bits=0)

    tag.write_page(0x04, b'\xDE\xAD\xBE\xEF')

    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd[:2] == bytes([0xA2, 0x04])
    assert cmd[2:] == b'\xDE\xAD\xBE\xEF'

    kwargs = mock_reader.transceive.call_args[1]
    assert kwargs.get('tx_crc') is True
    assert kwargs.get('rx_crc') is False


def test_t2t_write_page_invalid_length(mock_reader, tag):
    """验证 write_page 对非法长度数据抛出异常"""
    with pytest.raises(ValueError):
        tag.write_page(0x04, b'\x00' * 10)


def test_t2t_write_page_nak(mock_reader, tag):
    """验证 write_page 在收到 NAK 时抛出异常"""
    mock_reader.transceive.return_value = TransceiveResult(data=b'\x00', rx_bits=0)

    with pytest.raises(RuntimeError):
        tag.write_page(0x04, b'\xDE\xAD\xBE\xEF')


def test_t2t_write_page_no_response(mock_reader, tag):
    """验证 write_page 在无响应时抛出异常"""
    mock_reader.transceive.return_value = TransceiveResult(data=None, rx_bits=0)

    with pytest.raises(RuntimeError):
        tag.write_page(0x04, b'\xDE\xAD\xBE\xEF')


def test_t2t_read_ndef(mock_reader, tag):
    """验证 read_ndef 的 TLV 解析"""
    # CC page: E1 10 06 00 (NDEF capable, 48 bytes capacity)
    cc_page = b'\xE1\x10\x06\x00' + b'\x00' * 12
    # NDEF data: TLV T=03 L=04 V=AABBCCDD + Terminator FE in same 16-byte chunk
    ndef_page = b'\x03\x04\xAA\xBB\xCC\xDD\xFE\x00' + b'\x00' * 8
    empty_page = b'\x00' * 16

    mock_reader.transceive.side_effect = [
        TransceiveResult(data=cc_page, rx_bits=0),          # read_page(3) -> CC
        TransceiveResult(data=ndef_page, rx_bits=0),         # read_page(4) -> NDEF TLV + Terminator
        TransceiveResult(data=empty_page, rx_bits=0),        # read_page(8) -> padding
        TransceiveResult(data=empty_page, rx_bits=0),        # read_page(12) -> padding
    ]

    result = tag.read_ndef()

    assert result["ndef"] == b'\xAA\xBB\xCC\xDD'
    assert result["capacity"] == 48
