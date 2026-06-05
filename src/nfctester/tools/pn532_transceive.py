import time
from nfctester.trace import trace
from nfctester.hardware import SerialTransport
from nfctester.drivers import PN532_HSU

def run_atqa_poll_test():
    """
    PN532 Transceive 测试工具。
    使用 transceive 以 7-bit 格式发送 REQA (0x26) 或 WUPA (0x52)。
    """
    # --- 追踪配置 ---
    trace.set_layer("PROTOCOL", True)  # 开启协议追踪
    trace.set_layer("DRIVER", False)    # 开启底层驱动报文追踪
    trace.set_level("DEBUG")           # 设置日志级别
    # ----------------

    try:
        # 1. 初始化传输层
        transport = SerialTransport()
        
        # 2. 初始化驱动层
        reader = PN532_HSU(transport)
        
        # 3. 建立连接
        reader.connect()
        trace.info("开始循环轮询 (REQA/WUPA) (按 Ctrl+C 退出)...")
        #tag = reader.find()
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
                
                #reader.set_crc(True, False)
                #response = reader.transceive(b'\x50\x00')

                # 尝试寻卡
                reader.set_crc(False, False)
                #response = reader.transceive(b'\x52', last_tx_bits=7)
                response = reader.transceive(b'\x26', last_tx_bits=7)

                if response:
                    trace.success(f"收到响应 (ATQA) [cmd {b'\x26'.hex().upper()}]: {response.hex(' ').upper()}")
                    found = True
                    break # 找到卡片后跳出内层循环
            except Exception as e:
                # 忽略过程中的报错，继续尝试下一个命令或下一轮
                continue
            
            if not found:
                trace.debug("未检测到卡片响应")
            
            reader.set_rf_field(False)
            time.sleep(1)
            # 循环结束前保持 RF 场，不需要在此处强制关闭，下一次循环开始会自动处理或者由 finally 处理
            
    except KeyboardInterrupt:
        trace.info("测试已停止。")
    except Exception as e:
        trace.error(f"运行过程中发生错误: {e}")
    finally:
        if 'reader' in locals():
            #reader.set_rf_field(False)
            reader.disconnect()

if __name__ == "__main__":
    run_atqa_poll_test()
