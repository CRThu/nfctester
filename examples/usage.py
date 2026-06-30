"""
使用示例：Registry + Session

运行方式: uv run python examples/usage.py
"""
from nfctester.registry import TransportRegistry, CardReaderRegistry, session

# ============================================================
# 1. Registry: 类注册与实例化
# ============================================================
print("=== Transports ===")
for name in TransportRegistry.list():
    print(f"  - {name}")

print("\n=== Readers ===")
for name in CardReaderRegistry.list():
    print(f"  - {name}")

# 一行创建
reader = CardReaderRegistry.create("pn532", transport="serial", port="COM20")
print(f"\nCreated: {type(reader).__name__}")

# ============================================================
# 2. Session: 上下文管理器（自动 open/close）
# ============================================================

# 方式 A: 创建新 reader
# with session("pn532", transport="serial") as s:
#     tag = s.active()
#     if tag:
#         s.transceive_bits(b"\x26", last_tx_bits=7, tx_crc=False, rx_crc=False)

# 方式 B: 传入已有 reader
# with session(reader=reader) as s:
#     tag = s.active()

# ============================================================
# 3. CardRegistry: 卡片注册与动态实例化
# ============================================================
from nfctester.registry import CardRegistry

print("\n=== Cards ===")
for name in CardRegistry.list():
    print(f"  - {name}")

# 示例：动态创建卡片实例
# tag = reader.active()
# if tag:
#     card = CardRegistry.create("mifare_classic", reader=reader)
#     print(f"Card instance: {type(card).__name__}")
#     card.authenticate(0, b"\xFF"*6)
