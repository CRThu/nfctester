# nfctester 架构说明书 (AI 专用)

## 1. 项目概述
`nfctester` 是一个用于测试 RFID 卡片和读卡器的自动化测试框架。项目采用分层架构，旨在实现硬件通信、芯片驱动、卡片逻辑与加密算法的解耦。支持 PN532 和 CLRC663 两种读卡器，通过注册表机制实现无缝切换。

## 2. 九层架构体系

### 第一层：硬件传输层 (Hardware/Transport Layer)
*   **目录**: `src/nfctester/hardware/`
*   **职责**: 负责底层的字节流传输。
*   **核心类**: `Transport`（抽象基类）, `SerialTransport`（已注册为 `"serial"`）。
*   **设计原则**: 定义统一的 `Transport` 接口，通过 `@TransportRegistry.register()` 注册，支持扩展 TCP/IP 或 USB 传输。

### 第二层：驱动层 (Driver Layer)
*   **目录**: `src/nfctester/drivers/`
*   **职责**: 实现特定芯片的协议封装。
*   **已注册驱动**:
    *   `PN532_HSU`（注册为 `"pn532"`）: PN532 HSU 协议驱动，通过 NXP 标准帧格式通信。包含 ACK 处理、唤醒序列（Wakeup）、以及读取/写入数据帧。采用"请求-响应模式"，通过私有方法 `_req` 统一调度 `发送 -> 读取 -> 基础校验` 周期。
    *   `CLRC663`（注册为 `"clrc663"`）: CLRC663 UART 协议驱动，通过串口寄存器读写和 FIFO 命令机制与芯片通信。支持 ISO/IEC 14443A 协议，可无缝替换 PN532 读卡器。
*   **CardReader ABC 接口**（`card_reader.py`）:
    *   **数据结构**:
        *   `CardInfo`: 寻卡结果数据类，包含 `uid` (list[int])、`atq` (list[int])、`sak` (int)。仅包含硬件真实数据，不含推测信息。
        *   `TransceiveBits`: 收发结果数据类，包含 `data` (list[int]) 和 `bits` (int)（最后字节有效位数，0 = 整字节有效）。失败时返回空列表 `data=[]`。
    *   **生命周期**: `open()` 初始化硬件，`close()` 释放资源。
    *   **RF 控制**: `rf_field` 属性（getter/setter），开关物理天线驱动。
    *   **寻卡**: `active()` 模板方法（基类实现），内部调用子类 `_do_active()` 执行 REQA → anticoll → SELECT，寻卡成功后自动根据 ATQA/SAK 调用 `trace.set_parser()` 切换协议解析器。驱动子类只需实现 `_do_active()`。
    *   **Mifare**: `mf_crypto` 属性（读取加密引擎状态），`mf_auth(block, key_type, key, uid)`（执行 Mifare Classic 认证，成功后 `mf_crypto` 变为 True，后续 `transceive` 自动加密）。
    *   **数据交换**: `transceive(data, last_tx_bits=0, tx_crc=True, rx_crc=True)` 返回 `TransceiveBits`（含 `.data` 和 `.bits` 属性），支持位级发送。`last_tx_bits` 和 RX `bits` 信息通过 `trace.protocol(tx_bits=..., rx_bits=...)` 传递到 trace 层，在输出中显示为 `[N bits]` 标注。
    *   **CRC 控制**: `set_crc()` 已移除公开接口，CRC 通过 `transceive` 的 `tx_crc`/`rx_crc` 参数控制。驱动内部仍使用 `_set_crc()` 私有方法。
    *   **已移除**: `exchange()` 方法（合并入 `transceive`），`set_rf_field()`/`get_rf_field()` 方法（改为 `rf_field` 属性），`wakeup()`/`halt()` 方法（nfcscript 通过 raw transceive 实现）。
*   **CLRC663 驱动特点**:
    *   **UART 协议**: 使用 7 位地址 + R/W 位的寄存器读写协议。写操作发送 2 字节（地址 + 数据），读操作发送 1 字节（地址）并接收 1 字节（数据）。写操作后校验芯片回传的地址字节，不匹配时输出警告。
    *   **命令执行**: 通过写入 Command 寄存器启动命令，使用 FIFO 缓冲区交换数据，通过 IRQ0 寄存器轮询命令完成状态。
    *   **寻卡流程**: 手动实现 ISO 14443-A REQA → 抗冲突 → SELECT 序列，通过 TxDataNum 寄存器控制 7 位短帧（REQA）和标准帧（抗冲突/选择）。
    *   **Transceive 机制**: 底层 `_do_transceive()` 方法遵循 idle → flush FIFO → 写数据 → 清 IRQ → 启动命令的固定序列，确保每次通信状态干净。返回 `TransceiveBits`。
    *   **Mifare 硬件认证**: 使用 CLRC663 的 MFAuthent 命令（CMD_AUTHENT 0x0E），需要将密钥写入 Key RAM、UID 写入 UID RAM，认证成功后 `_mf_crypto_active` 标志置 True。
    *   **错误解码**: Error 寄存器位通过 `CLRC663_ERRORS` 字典映射为可读描述，`transceive()` 错误日志包含具体错误类型（如协议错误、碰撞、CRC 错误等）。
*   **PN532 驱动特点**:
    *   **寄存器辅助方法**: `_read_reg(address)` / `_write_reg(address, value)` / `_modify_reg(address, mask, value)`，用于直接操作 PN532 CIU 寄存器。
    *   **Mifare 硬件认证**: 使用 PN532 的 TgInitAsTarget 或 InDataExchange（指令 0x40），认证成功后 `_mf_crypto_active` 标志置 True，后续 `transceive` 自动切换到 InDataExchange。
*   **位帧收发支持**（PN532 与 CLRC663 均支持）:
    *   `transceive(data, last_tx_bits=0, tx_crc=True, rx_crc=True)`: 在标准整字节发送基础上支持位帧发送，返回 `TransceiveBits`。
        *   PN532: `last_tx_bits` 非 0 时，发送前写 `CIU_BitFraming`（`0x633D`）的 `TxLastBits[2:0]`，发送完成后清零复原。
        *   CLRC663: 通过修改 `TxDataNum`（`0x2E`）寄存器的 `TxLastBits[2:0]` 位域实现，发送完成后复原。
    *   `TransceiveBits.bits`: 直接在 `transceive` 返回值中携带最后接收字节的有效位数（0 = 全字节有效）。
        *   PN532: 读取 `CIU_Control`（`0x633C`）的 `RxLastBits[2:0]`。
        *   CLRC663: 读取 `RxBitCtrl`（`0x0C`）的 `RxLastBits[2:0]`。

### 注册表与会话系统 (Registry & Session)
*   **目录**: `src/nfctester/registry.py`
*   **职责**: 提供类注册与会话管理两大能力，贯穿硬件层与驱动层。
*   **核心组件**:
    *   `TransportRegistry`: 传输层类注册表。使用 `@TransportRegistry.register("name")` 装饰器注册 Transport 实现，`TransportRegistry.create("name", **kwargs)` 实例化。
    *   `CardReaderRegistry`: 读卡器类注册表。使用 `@CardReaderRegistry.register("name")` 装饰器注册 CardReader 实现。`CardReaderRegistry.create("name", transport="serial", **kwargs)` 可一行创建 reader（自动创建 transport 并注入）。
    *   `CardRegistry`: 卡片类注册表。使用 `@CardRegistry.register("name")` 装饰器注册 Card 实现。`CardRegistry.create("name", reader, **kwargs)` 可动态创建卡片实例。
    *   `ParserRegistry`: 协议解析器注册表。使用 `@ParserRegistry.register(atqa=..., sak=..., name=...)` 装饰器注册 ATQA/SAK → 解析器类映射，`get(atqa, sak)` 返回解析器类，`get_name(atqa, sak)` 返回显示名称，`list()` 返回所有已注册键。通过 `nfctester.ParserRegistry` 导出，支持外部扩展。
    *   `Session` / `session()`: 上下文管理器，封装 reader 的 open/close 生命周期，类似 C# 的 `using`。通过 `__getattr__` 委托所有 reader 方法调用，无需显式透传。
*   **入口点发现**: `load_entry_points()` 在包初始化时扫描 `nfctester.transports` / `nfctester.readers` entry-points，自动注册外部包的实现。
*   **外部扩展**: 外部脚本只需继承 `CardReader` 基类并用 `@CardReaderRegistry.register("name")` 装饰，import 即注册，无需打包。

### 第三层：卡片逻辑层 (Card Layer)
*   **目录**: `src/nfctester/cards/`
*   **职责**: 实现各种 RFID 卡片协议逻辑（如 ISO14443A, Mifare Classic）。
*   **核心类**: `BaseTag`, `BaseCard`, `MifareClassicCard`, `Type2Tag`。
*   **逻辑**: 
    *   **BaseTag**: 针对简单标签的基类，定义了通用的 `read_page` 和 `write_page` 接口。`transceive()` 透传到 reader 的 `transceive()` 并解包 `TransceiveBits.data`。
    *   **BaseCard**: 针对加密智能卡的基类，包含 `authenticate` 和钱包操作等复杂功能。
    *   `MifareClassicCard`: 继承自 `BaseCard`，实现完整的 Mifare Classic 指令集。`authenticate()` 内部调用 `reader.mf_auth()` 执行硬件认证，UID 由卡片自身的 `active()` 获取后传入。
    *   `Type2Tag`: 继承自 `BaseTag`，实现 NFC Forum Type 2 Tag 标准指令集（如 NTAG 读写）。`write_page` 使用 `transceive(cmd, tx_crc=True, rx_crc=False)` 控制 CRC。整合了 NDEF 解析能力 (`get_ndef`)。
    *   `NTAG21x`: 继承自 `Type2Tag`，针对 NXP NTAG21x 系列扩展了版本读取 (`get_version`) 和密码认证 (`auth`) 功能。
    *   `NTAG22x`: 继承自 `Type2Tag`，针对 NXP NTAG22x DNA 系列扩展了基于 AES-128 的双向互认证 (`auth`)。
    *   **认证逻辑**: Mifare Classic 的 `authenticate` 使用 reader 级别的 `mf_auth()` 硬件认证，需要 UID（由 `active()` 自动获取）。其他卡片类型的认证由各自的 `auth()` 方法处理。
    *   **构造约定**: 所有卡片类构造函数仅接收 `reader` 参数，不接收 `uid`。UID 通过 `active()` 或首次认证时自动获取。

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
*   **职责**: 提供中心化、解耦的日志处理子系统，区分物理层(driver)和协议层(protocol)的数据流监控。支持结构化 sink 回调，外部代码可注册回调接收 `TraceEvent` 对象，无需依赖 loguru 格式化输出。
*   **核心模块**: 
    *   `manager.py`: `TraceManager` 门面类，全局单例入口；注入对应解析器到各 Handler；提供 `set_parser(atqa, sak)` 根据 `ParserRegistry` 动态切换协议解析器，`add_sink(fn)` / `remove_sink(fn)` 注册结构化事件回调。
    *   `handler.py`: `TraceHandler`，管理流式追加与立即输出；接受 `BaseParser` 实例，调用 `TraceFormatter` 渲染。记录 `_last_tx` 上下文，RX 解析时传入 TX 命令用于匹配。`__call__` 支持 `tx_bits`/`rx_bits` 参数，非整字节时在输出中追加 `[N bits]` 标注（如 `TX ->  26 [7 bits]`）。TX 走命令解析链，RX 调用 `parser.parse_rx(data, tx)`，无匹配降级 raw hex。每次输出后构造 `TraceEvent` 通知所有 sink。
    *   `formatter.py`: `TraceFormatter`，提供 `format_raw()`（纯 hex）和 `format_summary()`（hex + 摘要标签）两种输出模式，均支持 `bits` 参数追加位级标注。
*   **TraceEvent 数据结构**:
    *   `layer`: "DRIVER" | "PROTOCOL"
    *   `direction`: "TX" | "RX"
    *   `raw`: 原始字节
    *   `parsed`: `ParsedFrame | None`（parse_level=0 时为 None）
    *   `summary`: 一行摘要（parse_level=1 时有值）
    *   `formatted`: 已渲染的文本消息
    *   `timestamp`: `time.time()`
*   **设计原则**: 严禁在驱动层使用硬编码的打印语句。通信日志必须通过 `trace` 的对应层级 Handler 统一输出，实现业务与日志的严格分离。

### 第七层：协议解析层 (Parsers Layer)
*   **目录**: `src/nfctester/parsers/`
*   **职责**: 将字节流解析为含语义描述的结构化数据，供 `TraceFormatter` 渲染，与日志层解耦。同时支持命令解析（TX）和响应解析（RX）两条路径。通过 `ParserRegistry` 注册 ATQA/SAK → 解析器类映射，寻卡时自动切换协议解析器。
*   **数据结构**:
    *   `ParsedField`: 单个字段（名称、原始字节、数值、描述、子字段列表）。
    *   `ParsedFrame`: 顶层结果（字段列表、帧标签、有效性标志）。
*   **核心模块**:
    *   `registry.py`: `ParserRegistry`，ATQA/SAK → 解析器类注册表。使用 `@ParserRegistry.register(atqa=..., sak=..., name=...)` 装饰器注册，`get(atqa, sak)` 返回匹配的解析器类，`get_name(atqa, sak)` 返回显示名称。支持外部扩展：新解析器只需 `from nfctester import ParserRegistry` 并用装饰器注册。
    *   `base_parser.py`: `BaseParser` 抽象基类，定义 `can_parse(data)` / `parse(data) -> ParsedFrame` 命令接口，以及 `parse_rx(data, tx=None) -> ParsedFrame | None` 响应接口（默认返回 None）。`tx` 参数提供 TX 命令上下文用于 RX 匹配。
    *   `table_parser.py`: `TableParser`，基于 `CMD_TABLE` 指令表的通用解析器基类。子类只需定义 `CMD_TABLE` 和可选的 `RESPONSES` dict，自动获得命令解析和单字节响应解析能力。
    *   `pn532_hsu_parser.py`: `PN532HSUParser`，解析 PN532 HSU 物理帧（ACK/NACK/Normal Frame），含 TFI/CMD/Status/Payload 子字段。
    *   `mifare_classic_parser.py`: `MifareClassicParser`，注册 3 个 ATQA/SAK 组合 (1K/4K/4K alt)，解析 Mifare Classic 指令层。`parse_rx` 基于 TX 命令匹配：ACK/NACK + READ 16 字节 block 数据。
    *   `t2t_parser.py`: `T2TParser`，注册 3 个 ATQA/SAK 组合 (T2T/Ultralight/Plus)，解析 NFC Forum Type 2 Tag 指令层。`parse_rx` 基于 TX 命令匹配：ACK/NACK + READ 页数据 + PWD_AUTH PACK + READ_SIG 签名。
*   **TX/RX 分离机制**: `TraceHandler` 记录 `_last_tx` 上下文。TX 使用 `can_parse()` + `parse()` 解析命令结构；RX 调用 `parse_rx(data, tx=_last_tx)`，parser 根据 TX 命令类型准确解析响应（如 READ→block 数据，WRITE→ACK），多字节或未知响应降级为 raw hex。
*   **设计原则**: 解析器只做结构化解析，不负责任何格式化输出。通过 `@ParserRegistry.register()` 声明 ATQA/SAK 映射，`TraceManager.set_parser(atqa, sak)` 在寻卡时动态切换。

### 第九层：脚本/CLI 层 (Scripts/CLI Layer)
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
    *   **测试分层**: 通过 pytest marker 区分单元测试和硬件测试：
        *   `@pytest.mark.unit`: 纯软件单元测试，无需硬件，mock reader。
        *   `@pytest.mark.hil`: 硬件在环测试，需要连接读卡器。
        *   细粒度 marker: `mifare`、`t2t`、`ntag21x`、`ntag224`，用于按卡片类型过滤 HIL 测试。
    *   **执行命令**:
        *   `uv run pytest` — 只跑单元测试（默认，`addopts = "-m 'not hil'"`）
        *   `uv run pytest -m hil --port COM4` — 跑全部 HIL 测试
        *   `uv run pytest -m "hil and mifare" --port COM4` — 只跑 Mifare HIL
        *   `uv run pytest -m "hil and (ntag21x or ntag224)" --port COM4` — 只跑 NTAG HIL
        *   `uv run pytest -m ""` — 跑全部（单元 + HIL）
    *   **Mock 测试**: 卡片协议层测试通过 mock `reader.transceive()` 返回已知响应向量，验证命令字节生成。共享 fixture 在 `tests/conftest.py` 的 `mock_reader` 中提供。
*   **配置**: 硬件参数（如 COM 端口）应通过环境变量 `NFCTESTER_PORT` 或命令行参数 `--port` / `--reader` 读取，严禁硬编码在核心库中。
*   **代码规范**: 
    *   方法和类必须有 Docstring。
    *   注释应简洁明了。
    *   异常处理必须覆盖超时和通信错误。

## 4. 外部项目集成指南

外部项目（如 `CarrotFMTester`）依赖 `nfctester` 时，应遵循以下规范：

*   **禁止直接 import 内部模块**: 不得 `from nfctester.hardware.serial_transport import SerialTransport` 或 `from nfctester.drivers.pn532_hsu import PN532_HSU`。这会耦合到具体实现，违反插件化设计。
*   **统一使用 Registry 创建读卡器**: `CardReaderRegistry.create("pn532", transport="serial", port="COM20")` 或 `CardReaderRegistry.create("clrc663", transport="serial", port="COM4")` 一行完成 transport + reader 的创建与注入。
*   **使用 Session 管理生命周期**: `with session("pn532", transport="serial", port="COM20") as s:` 或 `with session("clrc663", transport="serial", port="COM4") as s:` 自动处理 open/close，避免遗漏断开连接。
*   **卡片类接收 reader 实例**: 自定义卡片类（如 `SM7Card`）的构造函数应接受 `reader` 参数，不关心 reader 的创建方式。

## 5. 依赖项
*   `pyserial`: 串口通信。
*   `loguru`: 结构化日志记录。
*   `pytest`: 测试框架。
