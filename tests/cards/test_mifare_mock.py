import pytest
from unittest.mock import MagicMock
from nfctester.cards import MifareClassicCard
from nfctester.drivers.card_reader import CardInfo, TransceiveBits


UID = [0x01, 0x02, 0x03, 0x04]
KEY = [0xFF] * 6
BLOCK_ADDR = 0x04


@pytest.fixture
def card(mock_reader):
    return MifareClassicCard(mock_reader)


def test_mifare_auth(mock_reader, card):
    """验证 authenticate 调用 reader.mf_auth 的参数"""
    result = card.authenticate(BLOCK_ADDR, KEY, key_type=0x60)

    assert result is True
    mock_reader.active.assert_called_once()
    mock_reader.mf_auth.assert_called_once_with(BLOCK_ADDR, 0x60, KEY, UID)


def test_mifare_auth_keyb(mock_reader, card):
    """验证 KeyB 认证"""
    result = card.authenticate(BLOCK_ADDR, KEY, key_type=0x61)

    assert result is True
    mock_reader.mf_auth.assert_called_once_with(BLOCK_ADDR, 0x61, KEY, UID)


def test_mifare_read_block(mock_reader, card):
    """验证 read_block 生成的命令字节"""
    mock_reader.active.return_value = CardInfo(uid=UID, atq=[0x44, 0x00], sak=0x08)
    expected_data = list(range(16))
    mock_reader.transceive.return_value = TransceiveBits(data=expected_data, bits=0)

    result = card.read_block(BLOCK_ADDR)

    assert result == expected_data
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd == [0x30, BLOCK_ADDR]


def test_mifare_write_block(mock_reader, card):
    """验证 write_block 生成的命令字节"""
    mock_reader.active.return_value = CardInfo(uid=UID, atq=[0x44, 0x00], sak=0x08)
    data = list(range(16))
    mock_reader.transceive.return_value = TransceiveBits(data=[0x00], bits=0)

    result = card.write_block(BLOCK_ADDR, data)

    assert result is True
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd[:2] == [0xA0, BLOCK_ADDR]
    assert cmd[2:] == data


def test_mifare_write_block_invalid_length(mock_reader, card):
    """验证 write_block 对非法长度数据抛出异常"""
    mock_reader.active.return_value = CardInfo(uid=UID, atq=[0x44, 0x00], sak=0x08)

    with pytest.raises(ValueError):
        card.write_block(BLOCK_ADDR, [0x00] * 10)


def test_mifare_increment_block(mock_reader, card):
    """验证 increment_block 生成的命令字节"""
    mock_reader.active.return_value = CardInfo(uid=UID, atq=[0x44, 0x00], sak=0x08)
    mock_reader.transceive.return_value = TransceiveBits(data=[0x00], bits=0)

    result = card.increment_block(BLOCK_ADDR, 500)

    assert result is True
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd[:2] == [0xC1, BLOCK_ADDR]
    assert cmd[2:] == list((500).to_bytes(4, "little"))


def test_mifare_decrement_block(mock_reader, card):
    """验证 decrement_block 生成的命令字节"""
    mock_reader.active.return_value = CardInfo(uid=UID, atq=[0x44, 0x00], sak=0x08)
    mock_reader.transceive.return_value = TransceiveBits(data=[0x00], bits=0)

    result = card.decrement_block(BLOCK_ADDR, 200)

    assert result is True
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd[:2] == [0xC0, BLOCK_ADDR]
    assert cmd[2:] == list((200).to_bytes(4, "little"))


def test_mifare_restore_block(mock_reader, card):
    """验证 restore_block 生成的命令字节"""
    mock_reader.active.return_value = CardInfo(uid=UID, atq=[0x44, 0x00], sak=0x08)
    mock_reader.transceive.return_value = TransceiveBits(data=[0x00], bits=0)

    result = card.restore_block(BLOCK_ADDR)

    assert result is True
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd == [0xC2, BLOCK_ADDR]


def test_mifare_transfer_block(mock_reader, card):
    """验证 transfer_block 生成的命令字节"""
    mock_reader.active.return_value = CardInfo(uid=UID, atq=[0x44, 0x00], sak=0x08)
    mock_reader.transceive.return_value = TransceiveBits(data=[0x00], bits=0)

    result = card.transfer_block(BLOCK_ADDR)

    assert result is True
    cmd = mock_reader.transceive.call_args[0][0]
    assert cmd == [0xB0, BLOCK_ADDR]


def test_mifare_uid_cached(mock_reader, card):
    """验证 uid 只获取一次（通过 authenticate 触发 _ensure_uid）"""
    mock_reader.active.return_value = CardInfo(uid=UID, atq=[0x44, 0x00], sak=0x08)
    mock_reader.transceive.return_value = TransceiveBits(data=[0x00] * 16, bits=0)

    card.authenticate(0x04, KEY, key_type=0x60)
    card.read_block(0x04)

    assert mock_reader.active.call_count == 1
