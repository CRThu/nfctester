import pytest
from nfctester.crypto import MifareCrypto1

@pytest.mark.unit
def test_crypto1_encryption_decryption():
    """
    测试 MifareCrypto1 的加密和解密逻辑是否与已知结果一致
    """
    key_hex = "FFFFFFFFFFFF"
    plain_hex = "12345678"
    expected_cipher_hex = "EDAB4A1E"

    key = list(bytes.fromhex(key_hex))
    plain = list(bytes.fromhex(plain_hex))
    
    crypto = MifareCrypto1()
    
    # 执行加密
    crypto.initialize(key)
    cipher = crypto.encrypt(plain)
    cipher_result_hex = bytes(cipher).hex().upper()
    
    # 验证加密结果
    assert cipher_result_hex == expected_cipher_hex, f"加密结果不匹配: 实际 {cipher_result_hex}, 期望 {expected_cipher_hex}"
    
    # 执行解密（验证可逆性）
    crypto.initialize(key)
    decrypted = crypto.decrypt(cipher)
    decrypted_result_hex = bytes(decrypted).hex().upper()
    
    # 验证解密结果
    assert decrypted_result_hex == plain_hex.upper(), f"解密结果不匹配: 实际 {decrypted_result_hex}, 期望 {plain_hex.upper()}"
