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
# 2. Session: 上下文管理器（自动 connect/disconnect）
# ============================================================

# 方式 A: 创建新 reader
# with session("pn532", transport="serial") as s:
#     tag = s.find()
#     if tag:
#         s.set_crc(False, False)
#         s.transceive(b"\x26", last_tx_bits=7)

# 方式 B: 传入已有 reader
# with session(reader=reader) as s:
#     tag = s.find()
