import time
from nfctester.trace import trace
from nfctester.registry import CardReaderRegistry

def run_atqa_poll_test():
    """
    PN532 Transceive 测试工具。
    使用 transceive 以 7-bit 格式发送 REQA (0x26) 或 WUPA (0x52)。
    """
    # --- 追踪配置 ---
    trace.set_layer("PROTOCOL", True)  # 开启协议追踪
    trace.set_layer("DRIVER", False)    # 关闭底层驱动报文追踪
    trace.set_level("DEBUG")           # 设置日志级别
    # ----------------

    try:
        # 通过 Registry 创建读卡器
        reader = CardReaderRegistry.create("pn532", transport="serial")
        
        # 建立连接
        reader.open()
        trace.info("开始循环轮询 (REQA/WUPA) (按 Ctrl+C 退出)...")
        time.sleep(0.1)
        
        while True:
            # 开启 RF 场，并在循环中保持开启

            # reader.set_rf_field(False)
            # time.sleep(0.5)
            # reader.set_rf_field(True)
            # time.sleep(0.5)

            # 核心策略：先尝试发送 REQA (0x26)，如果失败尝试 WUPA (0x52)
            # 使用 transceive 配合 7-bit 模式
            
            found = False
            try:
                # 尝试寻卡
                res = reader.transceive([0x26], last_tx_bits=7, tx_crc=False, rx_crc=False)

                if res.data:
                    trace.success(f"收到响应 (ATQA) [cmd 26]: {res.data.hex(' ').upper()}")
                    found = True
                    break
            except Exception as e:
                # 忽略过程中的报错，继续尝试下一个命令或下一轮
                continue
            
            if not found:
                trace.debug("未检测到卡片响应")
            
            reader.rf_field = False
            time.sleep(1)
            
    except KeyboardInterrupt:
        trace.info("测试已停止。")
    except Exception as e:
        trace.error(f"运行过程中发生错误: {e}")
    finally:
        if 'reader' in locals():
            #reader.set_rf_field(False)
            reader.close()

if __name__ == "__main__":
    run_atqa_poll_test()
