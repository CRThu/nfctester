import time
from nfctester.trace import trace
from nfctester.registry import CardReaderRegistry

def run_scanner():
    """
    PN532 寻卡工具。
    采用项目解耦架构，支持循环侦测 ISO14443A 卡片。
    """
    try:
        # 通过 Registry 创建读卡器
        reader = CardReaderRegistry.create("pn532", transport="serial")
        
        # 建立连接
        reader.open()
        
        # 获取并显示固件版本
        version = reader.get_version()
        if version:
            trace.app(f"检测到 PN532 设备, 固件版本: {version.hex(' ').upper()}")
        
        trace.debug("开始循环寻卡 (按 Ctrl+C 退出)...")
        while True:
            # 寻卡
            card_info = reader.active()
            if card_info:
                uid = card_info.uid.hex(' ').upper()
                atq = card_info.atq.hex(' ').upper()
                sak = card_info.sak
                trace.app(f"发现卡片! UID: {uid} | ATQ: {atq} | SAK: 0x{sak:02X}")
            # 降低轮询频率
            time.sleep(0.5)

            # reader.set_crc(True, False)
            # response = reader.transceive(b'\x50\x00')
            # if response:
            #     trace.success(f"收到响应 (ATQA) [cmd {b'\x50\x00'.hex().upper()}]: {response.hex(' ').upper()}")
            # time.sleep(0.5)
            
            # reader.set_crc(False, False)
            # response = reader.transceive(b'\x52', last_tx_bits=7)
            # if response:
            #     trace.success(f"收到响应 (ATQA) [cmd {b'\x52'.hex().upper()}]: {response.hex(' ').upper()}")
            # time.sleep(0.5)

            # reader.set_rf_field(False)
            # time.sleep(0.5)
            # reader.set_rf_field(True)
            # time.sleep(0.5)

            # reader.set_crc(False, False)
            # response = reader.transceive(b'\x26', last_tx_bits=7)
            # if response:
            #     trace.success(f"收到响应 (ATQA) [cmd {b'\x26'.hex().upper()}]: {response.hex(' ').upper()}")
            # time.sleep(0.5)

    except KeyboardInterrupt:
        trace.debug("扫描已停止。")
    except Exception as e:
        trace.error(f"运行过程中发生错误: {e}")
    finally:
        if 'reader' in locals():
            reader.close()

if __name__ == "__main__":
    run_scanner()
