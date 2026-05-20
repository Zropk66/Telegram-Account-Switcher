"""
Telegram 设置数据块解析。

Telegram 桌面端将配置序列化为一系列“块”（Block）。每个块以一个 int32 的
ID 开头，后跟对应的变长数据。
"""
from enum import Enum
from io import BytesIO

from src.core.telegram_data_decrypter.qt import (
    read_qt_int32,
    read_qt_uint64,
    read_qt_byte_array,
    read_qt_utf8,
)


class SettingsBlocks(Enum):
    """设置数据块 ID 定义。"""
    dbiKey = 0x00
    dbiUser = 0x01
    dbiAutoStart = 0x06
    dbiStartMinimized = 0x07
    dbiSeenTrayTooltip = 0x0a
    dbiAutoUpdate = 0x0c
    dbiLastUpdateCheck = 0x0d
    dbiDefaultAttach = 0x11
    dbiSendToMenu = 0x1d
    dbiDialogLastPath = 0x23
    dbiRecentStickers = 0x26
    dbiMtpAuthorization = 0x4b
    dbiSessionSettings = 0x4d
    dbiLangPackKey = 0x4e
    dbiThemeKey = 0x54
    dbiTileBackground = 0x55
    dbiPowerSaving = 0x57
    dbiLanguagesKey = 0x5a
    dbiCacheSettings = 0x5c
    dbiApplicationSettings = 0x5e
    dbiFallbackProductionConfig = 0x60
    dbiBackgroundKey = 0x61
    dbiEncrypted = 444
    dbiVersion = 666


def read_boolean(data: BytesIO) -> bool:
    """读取 Qt int32 0/1 布尔值。"""
    return read_qt_int32(data) == 1


def read_settings_block(version: int, data: BytesIO, block_id: SettingsBlocks):
    """
    根据 Block ID 解析特定格式的块数据。
    """
    # 简单的基础类型块
    if block_id in (SettingsBlocks.dbiAutoStart, SettingsBlocks.dbiStartMinimized,
                    SettingsBlocks.dbiSendToMenu, SettingsBlocks.dbiSeenTrayTooltip,
                    SettingsBlocks.dbiAutoUpdate):
        return read_boolean(data)

    if block_id in (SettingsBlocks.dbiLastUpdateCheck, SettingsBlocks.dbiScalePercent,
                    SettingsBlocks.dbiPowerSaving):
        return read_qt_int32(data)

    if block_id in (SettingsBlocks.dbiFallbackProductionConfig,
                    SettingsBlocks.dbiApplicationSettings,
                    SettingsBlocks.dbiMtpAuthorization):
        return read_qt_byte_array(data)

    if block_id == SettingsBlocks.dbiDialogLastPath:
        return read_qt_utf8(data)

    if block_id == SettingsBlocks.dbiThemeKey:
        return {
            'day': read_qt_uint64(data),
            'night': read_qt_uint64(data),
            'night_mode': read_boolean(data)
        }

    if block_id == SettingsBlocks.dbiBackgroundKey:
        return {
            'day': read_qt_uint64(data),
            'night': read_qt_uint64(data)
        }

    if block_id == SettingsBlocks.dbiTileBackground:
        return {'day': read_qt_int32(data), 'night': read_qt_int32(data)}

    if block_id == SettingsBlocks.dbiLangPackKey:
        return read_qt_uint64(data)

    raise ValueError(f'未知 Block ID: {block_id}')


def read_settings_blocks(version: int, data: BytesIO) -> dict:
    """循环读取直到数据流耗尽，将所有块汇聚为字典。"""
    blocks = {}
    try:
        while True:
            block_id = SettingsBlocks(read_qt_int32(data))
            blocks[block_id] = read_settings_block(version, data, block_id)
    except StopIteration:
        pass
    return blocks
