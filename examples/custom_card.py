"""
示例：如何实现并注册一个自定义卡片
"""
from nfctester.registry import CardRegistry
from nfctester.cards.base_card import BaseCard

@CardRegistry.register("my_custom_card")
class MyCustomCard(BaseCard):
    def __init__(self, reader):
        super().__init__(reader)
        print("MyCustomCard initialized")

    def authenticate(self, block_addr: int, key: bytes, key_type: int) -> bool:
        print(f"Authenticating block {block_addr}...")
        return True

    def read_block(self, block_addr: int) -> bytes:
        return b"\x00" * 16

    def write_block(self, block_addr: int, data: bytes) -> bool:
        return True

    def increment_block(self, block_addr: int, value: int) -> bool:
        return True

    def decrement_block(self, block_addr: int, value: int) -> bool:
        return True

    def restore_block(self, block_addr: int) -> bool:
        return True

    def transfer_block(self, block_addr: int) -> bool:
        return True
