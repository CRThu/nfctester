import time
import sys
from crft.trace import trace
from crft.hardware import SerialTransport
from crft.drivers import PN532_HSU

def run_scanner():
    """
    PN532 寻卡工具。
    采用项目解耦架构，支持循环侦测 ISO14443A 卡片。
    """
    # 配置日志格式 (由 trace 统一管理，不再直接操作 logger)

    try:
        # 1. 初始化传输层 (自动识别环境配置中的串口)
        transport = SerialTransport()
        
        # 2. 初始化驱动层
        reader = PN532_HSU(transport)
        
        # 3. 建立连接
        reader.connect()
        
        # 4. 获取并显示固件版本
        version = reader.get_version()
        if version:
            trace.success(f"检测到 PN532 设备, 固件版本: {version.hex(' ').upper()}")
        
        trace.info("开始循环寻卡 (按 Ctrl+C 退出)...")
        while True:
            # 5. 寻卡
            tag = reader.find()
            if tag:
                uid = tag['uid'].hex(' ').upper()
                atq = tag['atq'].hex(' ').upper()
                sak = tag['sak']
                trace.success(f"发现卡片! UID: {uid} | ATQ: {atq} | SAK: 0x{sak:02X}")
            # 降低轮询频率
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        trace.info("扫描已停止。")
    except Exception as e:
        trace.error(f"运行过程中发生错误: {e}")
    finally:
        if 'reader' in locals():
            reader.disconnect()

if __name__ == "__main__":
    run_scanner()
