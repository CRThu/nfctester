import pytest
from nfctester.crypto import AES128Crypto

def test_aes128_ecb_vectors():
    """
    使用用户提供的数据集验证 AES-128 ECB 加解密
    """
    crypto = AES128Crypto()
    
    test_cases = [
        {
            "key": "00000000000000000000000000000000",
            "plaintext": "B9E2FC789B64BF237CCCAA20EC7E6E48",
            "ciphertext": "A04C124213C186F22399D33AC2A30215"
        },
        {
            "key": "00000000000000000000000000000000",
            "plaintext": "13C5DB8A5930439FC3DEF9A4C675360F",
            "ciphertext": "35C3E05A752E0144BAC0DE51C1F22C56"
        },
        {
            "key": "00000000000000000000000000000000",
            "plaintext": "D73F98C111912238766AFEBDBF9C64EF",
            "ciphertext": "B34408A23D8AEA266CAB947EA8E0118D"
        }
    ]
    
    print("\n=== AES-128 加解密校验开始 ===")
    passed = 0
    total = len(test_cases)
    
    for case in test_cases:
        key = bytes.fromhex(case["key"].replace(' ', ''))
        pt = bytes.fromhex(case["plaintext"].replace(' ', ''))
        ct_expected = bytes.fromhex(case["ciphertext"].replace(' ', ''))
        
        # 1. 执行加密
        ct_actual = crypto.encrypt(pt, key)
        result_hex = ct_actual.hex().upper()
        
        # 2. 校验
        if ct_actual == ct_expected:
            print(f"[PASS] 输入: {case['plaintext']} | 结果: {result_hex}")
            passed += 1
        else:
            print(f"[FAIL] 输入: {case['plaintext']} | 预期: {case['ciphertext']} | 实际: {result_hex}")
        
        # 3. 反向解密校验
        pt_actual = crypto.decrypt(ct_actual, key)
        if pt_actual != pt:
            print(f"  -> 解密失败!")
            
    print(f"\n测试总结: {passed} / {total} 成功\n")
    assert passed == total, f"AES-128 测试失败: {total - passed} 个用例未通过"

if __name__ == "__main__":
    test_aes128_ecb_vectors()