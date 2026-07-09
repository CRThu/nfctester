# nfctester 🥕

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.0.46-green.svg)](pyproject.toml)

`nfctester` 是一个专为 RFID/NFC 卡片与读卡器设计的自动化测试框架。项目采用严谨的分层架构设计，实现了硬件通信、芯片驱动、卡片逻辑与加密算法的深度解耦，旨在为 RFID 技术研究、漏洞分析及产品测试提供一个健壮且易于扩展的基础平台。支持 PN532 和 CLRC663 两种读卡器，通过注册表机制实现无缝切换。

## 🌟 核心特性

- **分层架构**: 清晰的 9 层体系结构，模块化程度高，易于维护与扩展。
- **广泛的协议支持**:
  - **卡片**: Mifare Classic, ISO14443A, NFC Forum Type 2 Tag (NTAG21x/22x 等)。
  - **芯片**: 深度优化 PN532 HSU 和 CLRC663 UART 驱动，均支持位帧 (Bit-framing) 收发。
- **强大加密支持**: 内置 AES-128 (CBC)、Mifare Crypto1 算法引擎，支持 NTAG22x AES 互认证。
- **可视化跟踪**: 跟踪控制层与协议解析层，提供结构化的通信日志输出（hex + 摘要标签），完美还原协议交互细节。
- **协议解析器自动切换**: 通过 `ParserRegistry` 注册 ATQA/SAK → 解析器映射，寻卡时自动切换协议解析器。
- **插件化扩展**: 通过 Registry 模式，外部只需 `.py` 文件 + 装饰器即可接入自定义读卡器和协议解析器，无需打包。

## 🏗️ 架构体系 (9-Layer Architecture)

项目遵循高度抽象的设计模式，分为以下九层：

1.  **硬件传输层 (Hardware)**: 负责底层字节流传输（如 `SerialTransport`）。
2.  **驱动层 (Driver)**: 实现特定芯片（如 PN532、CLRC663）的协议封装与寄存器操作。
3.  **注册表与会话 (Registry)**: 类注册（Transport/CardReader/Card/Parser）、会话管理，贯穿硬件层与驱动层。
4.  **卡片逻辑层 (Card)**: 定义各种 RFID 标签与智能卡的协议行为（Mifare, NTAG 等）。
5.  **加密算法层 (Crypto)**: 提供原子级的加密/解密操作（AES, Crypto1）。
6.  **通用工具层 (Utility)**: 包含 CRC 校验、位操作等基础辅助函数。
7.  **跟踪控制层 (Trace)**: 中心化的日志管理系统，实现业务逻辑与通信监控的分离。
8.  **协议解析层 (Parsers)**: 将字节流解析为结构化字段，供格式化输出使用。
9.  **脚本/CLI 层 (CLI)**: 提供开箱即用的命令行工具（如 `aes128-cli`、`pn532-scanner`）。

## 🚀 快速上手

### 环境准备

推荐使用 [uv](https://github.com/astral-sh/uv) 进行环境管理：

```bash
# 克隆仓库
git clone https://github.com/crthu/nfctester.git
cd nfctester

# 同步依赖
uv sync
```

### 基本用法：Registry 创建读卡器与卡片

```python
from nfctester.registry import CardReaderRegistry, CardRegistry

# 1. 一行创建读卡器（自动创建 transport 并注入）
reader = CardReaderRegistry.create("pn532", transport="serial", port="COM20")
reader.open()

# 2. 寻卡（自动切换协议解析器）
card_info = reader.active()
if card_info:
    # 假设已知卡片类型为 mifare_classic
    card = CardRegistry.create("mifare_classic", reader=reader)
    print(f"UID: {card_info.uid.hex(' ').upper()}")

reader.close()
```

### Session：上下文管理器（自动 open/close）

```python
from nfctester.registry import session

# 自动管理 reader 的生命周期，类似 C# 的 using
with session("pn532", transport="serial", port="COM20") as s:
    card_info = s.active()
    if card_info:
        res = s.transceive_bits(b"\x26", last_tx_bits=7, tx_crc=False, rx_crc=False)
        if res.data:
            print(f"ATQA: {res.data.hex(' ').upper()}")
# 退出时自动 close
```

### Mifare Classic 认证与读写

```python
with session("pn532", transport="serial", port="COM20") as s:
    card_info = s.active()
    if card_info:
        # 使用 reader 级别的硬件认证，uid 来自 active() 返回的 CardInfo
        if s.mf_auth(block=4, key_type=0x60, key=b'\xff\xff\xff\xff\xff\xff', uid=card_info.uid):
            # 认证后 transceive 自动走加密通道
            res = s.transceive(b'\x30\x04')  # READ block 4
            if res.data:
                print(f"Block 4: {res.data.hex(' ').upper()}")
```

## 🔌 自定义读卡器

框架通过 Registry 模式支持外部读卡器扩展。只需继承 `CardReader` 基类并用装饰器注册即可。

### 1. 自定义 Transport（可选）

如果你的硬件不是串口，先注册一个 Transport：

```python
from nfctester.registry import TransportRegistry
from nfctester.hardware.base import Transport

@TransportRegistry.register("tcp")
class TCPTransport(Transport):
    def __init__(self, host="127.0.0.1", port=5000):
        import socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

    def write(self, data: bytes):
        self.sock.sendall(data)

    def read(self, size: int) -> bytes:
        return self.sock.recv(size)

    def flush_input(self):
        self.sock.setblocking(False)
        try:
            while self.sock.recv(4096):
                pass
        except BlockingIOError:
            pass
        finally:
            self.sock.setblocking(True)

    def close(self):
        self.sock.close()
```

### 2. 自定义 CardReader

```python
from nfctester.registry import CardReaderRegistry
from nfctester.drivers.card_reader import CardReader, CardInfo, TransceiveBits

@CardReaderRegistry.register("acr122u")
class ACR122UReader(CardReader):
    def __init__(self, transport):
        self.transport = transport

    def open(self):
        self.transport.write(b"\xFF\x00\x00\x00\x00")
        self.transport.flush_input()

    def close(self):
        self.transport.close()

    def get_version(self) -> list[int]:
        self.transport.write(b"\xFF\x00\x48\x00\x00")
        return list(self.transport.read(10))

    @property
    def rf_field(self) -> bool:
        return True

    @rf_field.setter
    def rf_field(self, enabled: bool):
        pass

    def _do_active(self) -> CardInfo | None:
        cmd = b"\xD4\x4A\x01\x00"
        frame = bytes([0xFF, 0x00, 0x00, 0x00, len(cmd)]) + cmd
        self.transport.write(frame)
        res = self.transport.read(20)
        if res and len(res) >= 10:
            return CardInfo(uid=list(res[6:10]), atq=list(res[2:4]), sak=res[4])
        return None

    @property
    def mf_crypto(self) -> bool:
        return False

    def mf_auth(self, block: int, key_type: int, key: list[int], uid: list[int]) -> bool:
        return False

    def transceive(self, data: list[int], last_tx_bits: int = 0, tx_crc: bool = True, rx_crc: bool = True) -> TransceiveBits:
        frame = bytes([0xFF, 0x00, 0x00, 0x00, len(data)]) + bytes(data)
        self.transport.write(frame)
        res = self.transport.read(262)
        return TransceiveBits(data=list(res) if res else [], bits=0)
```

### 3. 使用你的自定义读卡器

```python
import my_reader  # import 即自动注册
from nfctester.registry import CardReaderRegistry

reader = CardReaderRegistry.create("acr122u", transport="serial", port="COM3")
reader.open()
card_info = reader.active()
reader.close()
```

### 4. 自定义协议解析器 (ParserRegistry)

注册自定义协议解析器，寻卡时自动切换：

```python
from nfctester import ParserRegistry
from nfctester.parsers.base_parser import BaseParser, ParsedFrame

@ParserRegistry.register(atqa=0x1234, sak=0x56, name="My Custom Protocol")
class MyProtocolParser(BaseParser):
    def can_parse(self, data: list[int]) -> bool:
        return len(data) > 0 and data[0] == 0xAA

    def parse(self, data: list[int]) -> ParsedFrame:
        # 解析 TX 命令
        ...

    def parse_rx(self, data: list[int], tx: list[int] | None = None) -> ParsedFrame | None:
        # 解析 RX 响应
        ...
```

### 5. 自定义卡片注册 (CardRegistry)

```python
from nfctester.registry import CardRegistry
from nfctester.cards.base_card import BaseCard

@CardRegistry.register("my_custom_card")
class MyCustomCard(BaseCard):
    # 实现 BaseCard 定义的抽象方法
    ...
```

### 6. 查看已注册的组件

```python
from nfctester.registry import TransportRegistry, CardReaderRegistry, CardRegistry
from nfctester.parsers.registry import ParserRegistry

print("Transports:", TransportRegistry.list())
print("Readers:", CardReaderRegistry.list())
print("Cards:", CardRegistry.list())
print("Parsers:", ParserRegistry.list())
```

更多示例见 [examples/](examples/) 目录。

## 🛠️ 运行工具

框架内置了多个实用的 CLI 工具：

- **PN532 扫描器**:
  ```bash
  uv run pn532-scanner
  ```
- **AES-128 加密工具**:
  ```bash
  uv run aes128-cli -m encrypt -i <hex_data> -k <hex_key>
  ```

## 🧪 运行测试

```bash
# 运行单元测试（默认，无需硬件）
uv run pytest

# 运行硬件在环测试（需连接读卡器）
uv run pytest -m hil --port COM4 --reader clrc663

# 按卡片类型过滤 HIL 测试
uv run pytest -m "hil and mifare" --port COM4
uv run pytest -m "hil and ntag224" --port COM20 --reader pn532

# 运行全部测试（单元 + HIL）
uv run pytest -m ""
```

## 📄 开源协议

本项目基于 **Apache License 2.0** 协议开源。详见 [LICENSE](LICENSE) 文件。
