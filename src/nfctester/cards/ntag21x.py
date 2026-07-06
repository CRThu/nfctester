from ..registry import CardRegistry
from .type2tag import Type2Tag


@CardRegistry.register("ntag21x")
class NTAG21x(Type2Tag):
    """
    NXP NTAG21x 系列专用驱动 (如 NTAG213, NTAG215, NTAG216)
    """

    CMD_GET_VERSION = 0x60
    CMD_PWD_AUTH = 0x1B

    def __init__(self, reader):
        super().__init__(reader)

    def get_version(self) -> list[int]:
        """
        发送 0x60 指令，获取 8 字节版本信息
        """
        cmd = [self.CMD_GET_VERSION]
        res = self.transceive(cmd)
        return res.data

    def auth(self, password: list[int]) -> list[int]:
        """
        发送 0x1B 指令进行密码认证
        认证流程说明：
        1. 发送 0x1B + 4字节 PWD。
        2. 如果 PWD 正确：芯片返回 2 字节的 PACK (Password Acknowledge)。
            - PACK 的值存储在配置区的特定地址（如 NTAG213 的 Page 0x2C 的 Byte 0-1）。
            - 默认值通常为 0x00 0x00，取决于生产商或之前的设置。
        3. 如果 PWD 错误：芯片返回 4-bit 的 NAK (通常为 0x0)。
            - 注意：驱动会将 NAK 视为传输错误或超时，返回0字节数据包。

        :param password: 4 字节密码
        :return: 2 字节的 PACK 响应
        """
        if len(password) != 4:
            raise ValueError("NTAG21x password must be 4 bytes")

        # 1. 组装指令: 0x1B + 4字节密码
        cmd = [self.CMD_PWD_AUTH] + list(password)

        # 2. 发送指令
        # 注意：如果认证失败，芯片会返回 4-bit 的 NAK (0x0)，
        # 许多读写器驱动（如 PN532）会将 NAK 转换成通信超时或传输错误异常。
        res = self.transceive(cmd)
        
        # 3. 验证响应
        if res.data is None or len(res.data) == 0:
            raise PermissionError("Authentication failed: No response (NAK)")

        # NTAG21x 认证成功会返回 2 字节的 PACK
        if len(res.data) == 2:
            return res.data
        else:
            raise PermissionError(f"Authentication failed: Unexpected response length {len(res.data)}")
