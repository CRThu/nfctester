import pytest
from nfctester.utils import crc_a

def test_crc_a_data_vector():
    """
    测试 CRC-A 数据向量校验。
    数据来源：需求给定的测试向量。
    """
    data = bytes.fromhex("DEADBEEF340300FE0000000000000000")
    expected = bytes.fromhex("D370") # D370 Little Endian
    assert crc_a(data) == expected
