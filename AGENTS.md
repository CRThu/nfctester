# nfctester 架构说明书 (AI 专用)

## 1. 项目概述
`nfctester` 是一个用于测试 RFID 卡片和 PN532 读卡器的自动化测试框架。项目采用分层架构，旨在实现硬件通信、芯片驱动、卡片逻辑与加密算法的解耦。

## 2. 八层架构体系

### 第一层：硬件传输层 (Hardware/Transport Layer)
*   **目录**: `src/nfctester/hardware/`
*   **职责**: 负责底层的字节流传输。
*   **核心类**: `Transport`（抽象基类）, `SerialTransport`（已注册为 `"serial"`）。
*   **设计原则**: 定义统一的 `Transport` 接口，通过 `@TransportRegistry.register()` 注册，支持扩展 TCP/IP 或 USB 传输。

### 第二层：驱动层 (Driver Layer)
*   **目录**: `src/nfctester/drivers/`
*   **职责**: 实现特定芯片的协议封装（如 PN532 的 NXP 标准帧格式）。
*   **核心类**: `PN532_HSU`（已注册为 `"pn532"`）。
*   **逻辑**: 包含 ACK 处理、唤醒序列（Wakeup）、以及读取/写入数据帧。
*   **模式**: 采用"请求-响应模式 (Request-Response Pattern)"，通过私有方法 `_req` 统一调度 `发送 -> 读取 -> 基础校验` 周期，确保指令执行的原子性与健壮性。
*   **寄存器辅助方法**:
    *   `_read_reg(address)`: 读取 16 位地址的寄存器值（PN532 指令 0x06）。
    *   `_write_reg(address, value)`: 写入寄存器（PN532 指令 0x08）。
    *   `_modify_reg(address, mask, value)`: 读-改-写，只修改 `mask` 指定的位域，其余位保持不变。`set_crc` 等方法均统一使用此接口。
*   **位帧收发支持**:
    *   `transceive(data, last_tx_bits=8)`: 在标准整字节发送基础上支持位帧发送。`last_tx_bits` 非 8 时，发送前写 `CIU_BitFraming`（`0x633D`）的 `TxLastBits[2:0]`，发送完成后清零复原，保证不影响后续整字节通信。
    *   `self.last_rx_bits`: 实例属性，每次 `transceive` 完成后自动更新为 `CIU_Control`（`0x633C`）的 `RxLastBits[2:0]`，供上层协议判断最后接收字节的有效位数（0 = 全字节有效）。

### 注册表与会话系统 (Registry & Session)
*   **目录**: `src/nfctester/registry.py`
*   **职责**: 提供类注册与会话管理两大能力，贯穿硬件层与驱动层。
*   **核心组件**:
    *   `TransportRegistry`: 传输层类注册表。使用 `@TransportRegistry.register("name")` 装饰器注册 Transport 实现，`TransportRegistry.create("name", **kwargs)` 实例化。
    *   `CardReaderRegistry`: 读卡器类注册表。使用 `@CardReaderRegistry.register("name")` 装饰器注册 CardReader 实现。`CardReaderRegistry.create("name", transport="serial", **kwargs)` 可一行创建 reader（自动创建 transport 并注入）。
    *   `Session` / `session()`: 上下文管理器，封装 reader 的 connect/disconnect 生命周期，类似 C# 的 `using`。通过 `__getattr__` 委托所有 reader 方法调用，无需显式透传。
*   **入口点发现**: `load_entry_points()` 在包初始化时扫描 `nfctester.transports` / `nfctester.readers` entry-points，自动注册外部包的实现。
*   **外部扩展**: 外部脚本只需继承 `CardReader` 基类并用 `@CardReaderRegistry.register("name")` 装饰，import 即注册，无需打包。

### 第三层：卡片逻辑层 (Card Layer)
*   **目录**: `src/nfctester/cards/`
*   **职责**: 实现各种 RFID 卡片协议逻辑（如 ISO14443A, Mifare Classic）。
*   **核心类**: `BaseTag`, `BaseCard`, `MifareClassicCard`, `Type2Tag`。
*   **逻辑**: 
    *   **BaseTag**: 针对简单标签的基类，定义了通用的 `read_page` 和 `write_page` 接口。
    *   **BaseCard**: 针对加密智能卡的基类，包含 `authenticate` 和钱包操作等复杂功能。
    *   `MifareClassicCard`: 继承自 `BaseCard`，实现完整的 Mifare Classic 指令集。
    *   `Type2Tag`: 继承自 `BaseTag`，实现 NFC Forum Type 2 Tag 标准指令集（如 NTAG 读写）。整合了 NDEF 解析能力 (`get_ndef`)。
    *   `NTAG21x`: 继承自 `Type2Tag`，针对 NXP NTAG21x 系列扩展了版本读取 (`get_version`) 和密码认证 (`auth`) 功能。
    *   `NTAG22x`: 继承自 `Type2Tag`，针对 NXP NTAG22x DNA 系列扩展了基于 AES-128 的双向互认证 (`auth`)。
    *   **认证逻辑**: `authenticate` 方法使用 PN532 内置的硬件认证功能。
    *   **协议安全**: 目前依赖硬件层处理 Mifare Classic 的三轮认证，加密算法层主要提供离线的算法验证支持。

### 第四层：加密算法层 (Crypto Layer)
*   **目录**: `src/nfctester/crypto/`
*   **职责**: 提供卡片交互所需的底层加密/解密原子操作。
*   **核心模块**: 
    *   `AES128Crypto`: 实现 AES-128 CBC 模式。
    *   `MifareCrypto1`: 有状态的流加密引擎，支持 Mifare Classic 认证。
*   **设计原则**: 
    *   **接口统一**: 继承 `BaseCrypto` 基类，确保 `encrypt` 和 `decrypt` 接口一致性。
    *   **状态隔离**: 对于 `MifareCrypto1` 等流加密，通过 `initialize` 严格管理内部 LFSR 状态；对于 `AES128Crypto` 等分组加密，则保持无状态设计。
*   **算法归口**: 包含算法特有的逻辑（如 Mifare 的 `prng_successor` 或 AES 的填充校验），确保算法实现的纯粹性，不包含卡片协议层逻辑。


### 第五层：通用工具层 (Utility Layer)
*   **目录**: `src/nfctester/utils/`
*   **职责**: 提供与硬件无关的通用算法或辅助函数（如 CRC 校验、数据格式转换）。
*   **核心模块**: 
    *   `crc`: 提供 `crc_a` 等标准校验算法。
    *   `BitOps`: 提供字节流的位操作（如 XOR、ROL 循环左移、ROR 循环右移），命名参考汇编指令。
*   **设计原则**: 保持模块化，不包含复杂类，仅提供原子函数。

### 第六层：跟踪控制层 (Trace Layer)
*   **目录**: `src/nfctester/trace/`
*   **职责**: 提供中心化、解耦的日志处理子系统，区分物理层(driver)和协议层(protocol)的数据流监控。
*   **核心模块**: 
    *   `manager.py`: `TraceManager` 门面类，全局单例入口；注入对应解析器到各 Handler。
    *   `handler.py`: `TraceHandler`，管理流式追加与立即输出；接受 `BaseParser` 实例，调用 `TraceFormatter` 渲染。
    *   `formatter.py`: `TraceFormatter`，接受 `ParsedFrame` 对象，渲染树状对齐输出（`[+]/[-]- 字段名 : hex  |-- 子字段`）。
*   **设计原则**: 严禁在驱动层使用硬编码的打印语句。通信日志必须通过 `trace` 的对应层级 Handler 统一输出，实现业务与日志的严格分离。

### 第七层：协议解析层 (Parsers Layer)
*   **目录**: `src/nfctester/parsers/`
*   **职责**: 将字节流解析为含语义描述的结构化字段树，供 `TraceFormatter` 渲染，与日志层解耦。
*   **数据结构**:
    *   `ParsedField`: 单个字段（名称、原始字节、数值、描述、子字段列表）。
    *   `ParsedFrame`: 顶层结果（字段列表、帧标签、有效性标志）。
*   **核心模块**:
    *   `base_parser.py`: `BaseParser` 抽象基类，定义 `can_parse(data)` 和 `parse(data) -> ParsedFrame` 接口。
    *   `pn532_hsu_parser.py`: `PN532HSUParser`，解析 PN532 HSU 物理帧（ACK/NACK/Normal Frame），含 TFI/CMD/Status/Payload 子字段。
    *   `mifare_classic_parser.py`: `MifareClassicParser`，解析剥离 PN532 封装后的 Mifare Classic 指令层（READ/AUTH/HALT）。
    *   `t2t_parser.py`: `T2TParser`，解析 NFC Forum Type 2 Tag 指令层（READ/WRITE/PWD_AUTH/HALT，ACK/NACK 响应）。
*   **设计原则**: 解析器只做结构化解析，不负责任何格式化输出。可通过 `TraceHandler(parser=XxxParser())` 按需注入，与具体协议无关。

### 第八层：脚本/CLI 层 (Scripts/CLI Layer)
*   **目录**: `src/nfctester/tools/`
*   **职责**: 提供命令行接口 (CLI) 以直接调用核心加密/通信逻辑。
*   **运行方式**: `uv run aes128-cli -m encrypt -i <hex> -k <key>`


## 3. 开发与测试指南

*   **环境管理**: 使用 `uv`。
*   **运行脚本**: 必须使用 `uv run <script_path>`。
*   **自动化测试**:
    *   使用 `pytest` 执行测试。
    *   测试结构与源码模块对齐：
        *   `tests/crypto/`: 算法层测试。
        *   `tests/cards/`: 卡片协议层测试。
        *   `tests/drivers/`: 硬件驱动层测试。
        *   `tests/utils/`: 通用工具层测试（如 CRC 校验）。
    *   执行特定模块测试: `uv run pytest tests/crypto/`
*   **配置**: 硬件参数（如 COM 端口）应通过环境变量 `NFCTESTER_PORT` 或配置文件读取，严禁硬编码在核心库中。
*   **代码规范**: 
    *   方法和类必须有 Docstring。
    *   注释应简洁明了。
    *   异常处理必须覆盖超时和通信错误。

## 4. 依赖项
*   `pyserial`: 串口通信。
*   `loguru`: 结构化日志记录。
*   `pytest`: 测试框架。