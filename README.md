# nfctester 🥕

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.0.37-green.svg)](pyproject.toml)

`nfctester` 是一个专为 RFID/NFC 卡片与 PN532 读卡器设计的自动化测试框架。项目采用严谨的分层架构设计，实现了硬件通信、芯片驱动、卡片逻辑与加密算法的深度解耦，旨在为 RFID 技术研究、漏洞分析及产品测试提供一个健壮且易于扩展的基础平台。

## 🌟 核心特性

- **分层架构**: 清晰的 8 层体系结构，模块化程度高，易于维护与扩展。
- **广泛的协议支持**:
  - **卡片**: Mifare Classic, ISO14443A, NFC Forum Type 2 Tag (NTAG21x/22x 等)。
  - **芯片**: 深度优化 PN532 HSU (High Speed UART) 驱动，支持位帧 (Bit-framing) 收发。
- **强大加密支持**: 内置 AES-128 (CBC)、Mifare Crypto1 算法引擎，支持 NTAG22x AES 互认证。
- **可视化跟踪**: 独特的跟踪控制层与协议解析层，提供树状结构化的通信日志输出，完美还原协议交互细节。
- **现代化工具链**: 基于 `uv` 进行包管理，集成 `pytest` 自动化测试与 `bump-my-version` 版本控制。

## 🏗️ 架构体系 (8-Layer Architecture)

项目遵循高度抽象的设计模式，分为以下八层：

1.  **硬件传输层 (Hardware)**: 负责底层字节流传输（如 `SerialTransport`）。
2.  **驱动层 (Driver)**: 实现特定芯片（如 PN532）的协议封装与寄存器操作。
3.  **卡片逻辑层 (Card)**: 定义各种 RFID 标签与智能卡的协议行为（Mifare, NTAG 等）。
4.  **加密算法层 (Crypto)**: 提供原子级的加密/解密操作（AES, Crypto1）。
5.  **通用工具层 (Utility)**: 包含 CRC 校验、位操作等基础辅助函数。
6.  **跟踪控制层 (Trace)**: 中心化的日志管理系统，实现业务逻辑与通信监控的分离。
7.  **协议解析层 (Parsers)**: 将字节流解析为结构化字段树，供格式化输出使用。
8.  **脚本/CLI 层 (CLI)**: 提供开箱即用的命令行工具。

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

### 运行工具

框架内置了多个实用的 CLI 工具：

- **PN532 扫描器**:
  ```bash
  uv run pn532-scanner
  ```
- **AES-128 加密工具**:
  ```bash
  uv run aes128-cli -m encrypt -i <hex_data> -k <hex_key>
  ```

### 运行测试

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
