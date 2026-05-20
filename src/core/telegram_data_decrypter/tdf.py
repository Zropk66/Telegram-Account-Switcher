"""TDF 文件格式解析模块。

TDF（Telegram Data File）是 Telegram 桌面端用于存储加密数据的容器格式。
文件结构简单，包含版本号和加密的有效载荷。

文件格式：
- 前 4 字节：版本号（小端序 int32）
- 后续字节：加密数据（包含盐值、加密密钥和加密信息）

典型用法::

    from src.core.telegram_data_decrypter.tdf import parse_raw_tdf

    with open('key_datas', 'rb') as f:
        tdf = parse_raw_tdf(f.read())
    print(f"版本: {tdf.version}")
"""

from dataclasses import dataclass


@dataclass
class RawTdfFile:
    """原始 TDF 文件数据结构。

    属性:
        version: 文件格式版本号
        encrypted_data: 加密的有效载荷数据
    """
    version: int
    encrypted_data: bytes


def parse_raw_tdf(raw_data: bytes) -> RawTdfFile:
    """解析原始 TDF 文件数据。

    从字节数据中提取版本号和加密数据。

    参数:
        raw_data: 从磁盘读取的原始文件内容

    返回:
        解析后的 RawTdfFile 对象
    """
    # 前 4 字节是小端序的版本号
    version = int.from_bytes(raw_data[:4], 'little')
    encrypted_data = raw_data[4:]

    return RawTdfFile(version, encrypted_data)
