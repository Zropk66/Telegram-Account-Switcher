"""TDF 文件格式解析模块。

TDF（Telegram Data File）是 Telegram 桌面端用于存储加密数据的文件格式。
文件结构：4 字节魔数 + 4 字节版本号 + 加密数据 + 16 字节 MD5 校验和。
"""

import hashlib

# TDF 文件的魔数标识，所有 TDF 文件都以这 4 个字节开头
TDF_MAGIC = b'TDF$'


class TdfParserError(Exception):
    """TDF 解析过程中的通用错误基类。"""
    pass


class WrongMagicTdfParserError(Exception):
    """文件魔数不匹配，不是合法的 TDF 文件。"""
    pass


class WrongHashsumTdfParserError(Exception):
    """MD5 校验和不匹配，文件可能已损坏。"""
    pass


class RawTdfFile:
    """解析后的 TDF 文件对象，包含版本号、加密数据和校验和。"""

    def __init__(self):
        self.version = None       # 文件格式版本号（小端序 uint32）
        self.encrypted_data = None  # 加密载荷的原始字节
        self.hashsum = None       # 文件尾部的 MD5 校验和


def parse_raw_tdf(data: bytes) -> RawTdfFile:
    """解析原始 TDF 文件字节，校验魔数和 MD5 完整性后返回 RawTdfFile 对象。"""
    if data[:4] != TDF_MAGIC:
        raise WrongMagicTdfParserError('Wrong magic. Not a TDF file?')

    tdf = RawTdfFile()

    tdf.version = int.from_bytes(data[4:8], 'little')
    tdf.encrypted_data = data[8:-16]
    tdf.hashsum = data[-16:]

    # 重新计算 MD5 并与文件中存储的校验和比对
    actual_md5 = hashlib.md5(
        tdf.encrypted_data +
        len(tdf.encrypted_data).to_bytes(4, 'little') +
        tdf.version.to_bytes(4, 'little') +
        TDF_MAGIC
    ).digest()

    if actual_md5 != tdf.hashsum:
        raise WrongHashsumTdfParserError('Wrong hashsum. Corrupted file?')

    return tdf
