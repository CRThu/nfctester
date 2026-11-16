# AGENTS.md: nfctester 架构规范与开发手册 (AI 专用)

## 1. 项目概述与定位
`nfctester` 是一个高内聚、低耦合的 RFID/NFC 自动化测试与硬件抽象框架。采用纯插件化分层架构，实现硬件通信、芯片驱动、卡片逻辑、加密算法与协议解析的严格解耦。支持 PN532 和 CLRC663 读卡器，通过注册表机制实现无缝切换。

## 2. 核心分层架构

```text
 1. 硬件传输 (Hardware): Transport (ABC) -> SerialTransport (注册为 "serial")
 2. 读卡器驱动 (Drivers): CardReader (ABC) -> PN532_HSU ("pn532"), CLRC663 ("clrc663")
 3. 注册表与会话 (Registry): TransportRegistry / CardReaderRegistry / CardRegistry / ParserRegistry / Session
 4. 卡片逻辑 (Cards): BaseTag / BaseCard -> Type2Tag, NTAG21x, NTAG22x, MifareClassicCard
 5. 加密算法 (Crypto): BaseCrypto -> AES128Crypto, MifareCrypto1
 6. 通用工具 (Utils): crc (crc_a), BitOps (位旋转与掩码)
 7. 跟踪与事件 (Trace): TraceManager (全局单例) -> TraceHandler -> TraceFormatter & Event Sinks
 8. 协议解析 (Parsers): BaseParser / TableParser -> PN532HSUParser, MifareClassicParser, T2TParser
 9. 命令行工具 (Tools): aes128-cli 等
```

- **统一 CardReader 契约 (`CardReader`)**：
  - **物理硬件属性**：`name` (只读驱动名), `fifo_size` (硬件 FIFO 深度常量), `lazy_crc` (原生惰性 CRC 缓存开关), `rf_field` (天线场开关)。
  - **核心生命周期与操作**：`open()`, `close()`, `active()`, `transceive(...)`。
  - **位帧与非整字节契约**：`transceive(data, last_tx_bits=0, tx_crc=True, rx_crc=True) -> TransceiveBits`。支持短帧控制（如 7-bit REQA、4-bit ACK/NAK）；`TransceiveBits` 携带 `.data` 和 `.bits`（0=全字节有效，1~7 表示最后字节有效位），trace 自动渲染 `[N bits]`。
  - **Mifare 硬件认证契约**：`mf_auth(block, key_type, key, uid)` 执行硬件认证；成功后内部 `mf_crypto` 置 `True`，后续 `transceive` 自动透明启用硬件流加密。
  - **CRC 动态控制契约**：历史 `set_crc()` 已彻底移除，严禁外部调用；CRC 完全通过 `transceive` 的 `tx_crc`/`rx_crc` 参数动态控制。
  - **核心数据模型**：`CardInfo(uid, atq, sak)`（仅反映物理层真实数据，无推测数据）。

## 3. 插件化扩展契约 (Registry Extension Protocols)

系统核心组件统一由注册表管理，外部扩展通过装饰器即插即用，严禁在外部直接 import 具体底层驱动实现类：

1. **传输层扩展**：继承 `Transport`，使用 `@TransportRegistry.register("name")` 装饰；
2. **读卡器扩展**：继承 `CardReader`，实现 `_do_active()` 与 `transceive()`，使用 `@CardReaderRegistry.register("name")` 装饰；
3. **卡片协议扩展**：简单标签继承 `BaseTag`，安全/加密卡继承 `BaseCard`。卡片构造函数**仅接收 `reader` 实例**（不接 UID，UID 在 `active()` 寻卡后获取），使用 `@CardRegistry.register("name")` 装饰；
4. **协议解析器扩展**：继承 `BaseParser` 或 `TableParser`，使用 `@ParserRegistry.register(atqa=..., sak=..., name=...)` 装饰。`CardReader.active()` 寻卡成功后自动根据 ATQA/SAK 联动 `trace.set_parser()` 动态切换解析器。

## 4. 跟踪系统与协议解析 (Trace & Event Architecture)

- **业务与日志物理解耦**：驱动层严禁手写 `print()`。所有底层物理帧与协议交互必须通过 `trace.driver` 或 `trace.protocol` 统一输出。
- **结构化 Sink 回调**：外部系统可通过 `TraceManager.add_sink(callback)` 监听结构化 `TraceEvent`（包含 layer, direction, raw, parsed, summary, timestamp），无需依赖文本日志解析。
- **TX/RX 上下文感知**：`TraceHandler` 维护 `_last_tx`，在 RX 到达时注入 `parser.parse_rx(data, tx=_last_tx)`，实现请求-响应精确关联解析（如 WRITE 回应 ACK，READ 回应 Payload）。

## 5. 测试与质量保障 (Testing Discipline)

采用分层测试策略，区分纯软件单元测试与硬件在环测试（HIL）：

```bash
# 1. 纯软件单元测试（无需物理硬件，通过 mock reader 跑通逻辑）
uv run pytest                          # 默认执行: -m "not hil"

# 2. 硬件在环测试（需连接真实读卡器与卡片）
uv run pytest -m hil --port COM4       # 运行全量硬件测试
uv run pytest -m "hil and mifare"      # 按卡片类型过滤 (mifare, t2t, ntag21x, ntag224)
```

- **Mock 规范**：卡片与协议层测试统一通过 `tests/conftest.py` 中的 `mock_reader` 注入已知响应向量，断言命令字节与状态机流转。

## 6. 核心工程红线

1. **依赖与生命周期安全**：
   - 外部调用必须统一使用 `CardReaderRegistry.create(name, transport=...)` 或 `with session(name, ...) as reader:`，严禁手动直接实例化具体驱动类（如 `from ...pn532_hsu import PN532_HSU`）。
   - 退出上下文或进程时必须确保 RF 场与传输句柄被彻底释放。
2. **零硬件伪兜底**：
   - 硬件不支持的功能（如非法的位帧格式或不支持的速率）必须显式抛出异常，严禁在驱动层使用静默跳过或软件伪造。
3. **配置解耦**：
   - 串口号、波特率等硬件参数统一通过环境变量（`NFCTESTER_PORT`）或 CLI 参数传入，严禁硬编码在核心库中。
