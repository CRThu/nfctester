import pytest
from nfctester.cards import Type2Tag
from nfctester.drivers.card_reader import TransceiveBits


@pytest.fixture
def tag(mock_reader):
    return Type2Tag(mock_reader)


def test_t2t_read_page(mock_reader, tag):
    """验证 read_page 生成的 READ 命令"""
    page_data = list(range(16))
    mock_reader.transceive.return_value = TransceiveBits(data=page_data, bits=0)

    result = tag.read_page(0x04)

    assert result == page_data
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd == [0x30, 0x04]


def test_t2t_read_page_no_response(mock_reader, tag):
    """验证 read_page 在无响应时抛出异常"""
    mock_reader.transceive.return_value = TransceiveBits(data=None, bits=0)

    with pytest.raises(RuntimeError):
        tag.read_page(0x04)


def test_t2t_write_page(mock_reader, tag):
    """验证 write_page 生成的 WRITE 命令和参数"""
    mock_reader.transceive.return_value = TransceiveBits(data=[0x0A], bits=0)

    tag.write_page(0x04, [0xDE, 0xAD, 0xBE, 0xEF])

    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd[:2] == [0xA2, 0x04]
    assert cmd[2:] == [0xDE, 0xAD, 0xBE, 0xEF]

    kwargs = mock_reader.transceive.call_args[1]
    assert kwargs.get('tx_crc') is True
    assert kwargs.get('rx_crc') is False


def test_t2t_write_page_invalid_length(mock_reader, tag):
    """验证 write_page 对非法长度数据抛出异常"""
    with pytest.raises(ValueError):
        tag.write_page(0x04, [0x00] * 10)


def test_t2t_write_page_nak(mock_reader, tag):
    """验证 write_page 在收到 NAK 时抛出异常"""
    mock_reader.transceive.return_value = TransceiveBits(data=[0x00], bits=0)

    with pytest.raises(RuntimeError):
        tag.write_page(0x04, [0xDE, 0xAD, 0xBE, 0xEF])


def test_t2t_write_page_no_response(mock_reader, tag):
    """验证 write_page 在无响应时抛出异常"""
    mock_reader.transceive.return_value = TransceiveBits(data=None, bits=0)

    with pytest.raises(RuntimeError):
        tag.write_page(0x04, [0xDE, 0xAD, 0xBE, 0xEF])


def test_t2t_read_ndef(mock_reader, tag):
    """验证 read_ndef 的 TLV 解析"""
    # CC page: E1 10 06 00 (NDEF capable, 48 bytes capacity)
    cc_page = list(bytes([0xE1, 0x10, 0x06, 0x00]) + b'\x00' * 12)
    # NDEF data: TLV T=03 L=04 V=AABBCCDD + Terminator FE in same 16-byte chunk
    ndef_page = list(bytes([0x03, 0x04, 0xAA, 0xBB, 0xCC, 0xDD, 0xFE, 0x00]) + b'\x00' * 8)
    empty_page = [0x00] * 16

    mock_reader.transceive.side_effect = [
        TransceiveBits(data=cc_page, bits=0),          # read_page(3) -> CC
        TransceiveBits(data=ndef_page, bits=0),         # read_page(4) -> NDEF TLV + Terminator
        TransceiveBits(data=empty_page, bits=0),        # read_page(8) -> padding
        TransceiveBits(data=empty_page, bits=0),        # read_page(12) -> padding
    ]

    result = tag.read_ndef()

    assert result["ndef"] == [0xAA, 0xBB, 0xCC, 0xDD]
    assert result["capacity"] == 48
