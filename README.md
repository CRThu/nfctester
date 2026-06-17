# nfctester 🥕

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.0.38-green.svg)](pyproject.toml)

`nfctester` 是一个专为 RFID/NFC 卡片与 PN532 读卡器设计的自动化测试框架。项目采用严谨的分层架构设计，实现了硬件通信、芯片驱动、卡片逻辑与加密算法的深度解耦，旨在为 RFID 技术研究、漏洞分析及产品测试提供一个健壮且易于扩展的基础平台。

## 🌟 核心特性

- **分层架构**: 清晰的 8 层体系结构，模块化程度高，易于维护与扩展。
- **广泛的协议支持**:
  - **卡片**: Mifare Classic, ISO14443A, NFC Forum Type 2 Tag (NTAG21x/22x 等)。
  - **芯片**: 深度优化 PN532 HSU (High Speed UART) 驱动，支持位帧 (Bit-framing) 收发。
- **强大加密支持**: 内置 AES-128 (CBC)、Mifare Crypto1 算法引擎，支持 NTAG22x AES 互认证。
- **可视化跟踪**: 独特的跟踪控制层与协议解析层，提供树状结构化的通信日志输出，完美还原协议交互细节。
- **插件化扩展**: 通过 Registry 模式，外部只需 `.py` 文件 + 装饰器即可接入自定义读卡器，无需打包。

## 🏗️ 架构体系 (8-Layer Architecture)

项目遵循高度抽象的设计模式，分为以下八层：

1.  **硬件传输层 (Hardware)**: 负责底层字节流传输（如 `SerialTransport`）。
2.  **驱动层 (Driver)**: 实现特定芯片（如 PN532）的协议封装与寄存器操作。
3.  **注册表与会话 (Registry)**: 类注册、会话管理，贯穿硬件层与驱动层。
4.  **卡片逻辑层 (Card)**: 定义各种 RFID 标签与智能卡的协议行为（Mifare, NTAG 等）。
5.  **加密算法层 (Crypto)**: 提供原子级的加密/解密操作（AES, Crypto1）。
6.  **通用工具层 (Utility)**: 包含 CRC 校验、位操作等基础辅助函数。
7.  **跟踪控制层 (Trace)**: 中心化的日志管理系统，实现业务逻辑与通信监控的分离。
8.  **协议解析层 (Parsers)**: 将字节流解析为结构化字段树，供格式化输出使用。
9.  **脚本/CLI 层 (CLI)**: 提供开箱即用的命令行工具。

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
reader.connect()

# 2. 通过 CardRegistry 动态创建卡片实例
tag = reader.find()
if tag:
    # 假设已知卡片类型为 mifare_classic
    card = CardRegistry.create("mifare_classic", reader=reader)
    print(f"UID: {card.uid.hex(' ').upper()}")

reader.disconnect()
```

### Session：上下文管理器（自动 connect/disconnect）

```python
from nfctester.registry import session

# 自动管理 reader 的生命周期，类似 C# 的 using
with session("pn532", transport="serial", port="COM20") as s:
    tag = s.find()
    if tag:
        s.set_crc(False, False)
        s.transceive(b"\x26", last_tx_bits=7)
# 退出时自动 disconnect
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
from nfctester.drivers import CardReader

@CardReaderRegistry.register("acr122u")
class ACR122UReader(CardReader):
    def __init__(self, transport):
        self.transport = transport

    def connect(self):
        self.transport.write(b"\xFF\x00\x00\x00\x00")
        self.transport.flush_input()

    def get_version(self) -> bytes:
        self.transport.write(b"\xFF\x00\x48\x00\x00")
        return self.transport.read(10)

    def set_crc(self, tx_enabled: bool, rx_enabled: bool):
        pass

    def set_rf_field(self, enabled: bool):
        pass

    def get_rf_field(self) -> bool:
        return True

    def find(self) -> dict:
        cmd = b"\xD4\x4A\x01\x00"
        frame = bytes([0xFF, 0x00, 0x00, 0x00, len(cmd)]) + cmd
        self.transport.write(frame)
        res = self.transport.read(20)
        if res and len(res) >= 10:
            return {"uid": res[6:10], "atq": res[2:4], "sak": res[4]}
        return None

    def select(self) -> dict:
        return self.find()

    def deselect(self) -> bool:
        return True

    def exchange(self, data: bytes) -> bytes:
        frame = bytes([0xFF, 0x00, 0x00, 0x00, len(data)]) + data
        self.transport.write(frame)
        return self.transport.read(262)

    def transceive(self, data: bytes, last_tx_bits: int = 0) -> bytes:
        return self.exchange(data)

    def disconnect(self):
        self.transport.close()
```

### 3. 使用你的自定义读卡器

```python
import my_reader  # import 即自动注册
from nfctester.registry import CardReaderRegistry

reader = CardReaderRegistry.create("acr122u", transport="serial", port="COM3")
reader.connect()
tag = reader.find()
reader.disconnect()
```

### 4. 自定义卡片注册 (CardRegistry)

查看 `examples/custom_card.py` 以获取如何实现自定义卡片类的示例：

```python
from nfctester.registry import CardRegistry
from nfctester.cards.base_card import BaseCard

@CardRegistry.register("my_custom_card")
class MyCustomCard(BaseCard):
    # 实现 BaseCard 定义的抽象方法
    ...
```

### 5. 查看已注册的组件

```python
from nfctester.registry import TransportRegistry, CardReaderRegistry, CardRegistry

print("Transports:", TransportRegistry.list())
print("Readers:", CardReaderRegistry.list())
print("Cards:", CardRegistry.list())
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
# 运行所有测试
uv run pytest

# 运行特定模块测试（如加密模块）
uv run pytest tests/crypto/
```

## 📄 开源协议

本项目基于 **Apache License 2.0** 协议开源。详见 [LICENSE](LICENSE) 文件。

---
*本README由 Gemini 3 Flash 生成*
