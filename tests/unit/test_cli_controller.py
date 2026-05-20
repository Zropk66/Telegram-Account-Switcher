"""
CLIController 命令行控制器单元测试。

验证命令行参数解析、配置检查、标签回退以及批量加解密操作的控制流程。
"""
from unittest.mock import patch, MagicMock


def test_parse_switch_with_tag(mock_config, mock_logger):
    """验证 `-s tag` 参数会被解析为目标切换标签。"""
    from src.core.cli_controller import CLIController

    cli = CLIController(
        config=mock_config,
        logger=mock_logger,
        help_handler=None,
        settings_handler=None,
        info_handler=None,
        warning_handler=None,
        error_handler=None
    )

    with patch('sys.argv', ['tas', '-s', 'account1']):
        args = cli.parse_args()
        assert args.switch == 'account1'

    with patch.object(cli, '_validate_tag', return_value='account1'):
        tag = cli._apply_args(args)
        assert tag == 'account1'


def test_parse_encrypt_with_password(mock_config, mock_logger):
    """验证加密参数和密码参数能正确写入运行时配置。"""
    from src.core.cli_controller import CLIController

    cli = CLIController(
        config=mock_config,
        logger=mock_logger
    )

    with patch('sys.argv', ['tas', '-e', '-p', 'my_secret_pass']):
        args = cli.parse_args()
        assert args.encrypt is True
        assert args.password == 'my_secret_pass'

    args.password = 'test_pass'
    cli._apply_args(args)
    assert mock_config.pwd == 'test_pass'


def test_check_config_valid(mock_config, mock_logger):
    """验证客户端路径、账户目录和默认账户完整时配置检查通过。"""
    from src.core.cli_controller import CLIController

    cli = CLIController(
        config=mock_config,
        logger=mock_logger
    )

    with patch('src.core.cli_controller.search_file_in_dirs', return_value='tdata-default'):
        with patch('src.core.cli_controller.Path') as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.is_file.return_value = True
            mock_path_instance.is_dir.return_value = True
            mock_path.return_value = mock_path_instance

            args = MagicMock()
            args.switch = None
            args.password = None
            args.key_login = False

            result = cli.check_config(args)

            assert result is True
            mock_config.sync_all_account_paths.assert_called_once()


def test_check_config_client_not_found(mock_config, mock_logger):
    """验证客户端可执行文件缺失时，命令行流程会中止并记录错误。"""
    from src.core.cli_controller import CLIController

    cli = CLIController(
        config=mock_config,
        logger=mock_logger
    )

    with patch('src.core.cli_controller.search_file_in_dirs', return_value=None):
        with patch('src.core.cli_controller.Path') as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.is_file.return_value = False
            mock_path_instance.is_dir.return_value = True
            mock_path.return_value = mock_path_instance

            args = MagicMock()
            args.switch = None
            args.password = None
            args.key_login = False

            result = cli.check_config(args)

            assert result is False
            mock_logger.exception.assert_called_once()


def test_validate_tag_invalid_fallback_default(mock_config, mock_logger):
    """验证无效目标标签会回退到默认账户，避免切换到不存在的目录。"""
    from src.core.cli_controller import CLIController

    mock_config.default = 'default_account'
    mock_config.tags = {'account1': {}}

    cli = CLIController(
        config=mock_config,
        logger=mock_logger
    )

    with patch('src.core.cli_controller.search_file_in_dirs', return_value=None):
        result = cli._validate_tag('invalid_tag')
        assert result == 'default_account'
        mock_logger.warning.assert_called_once()

    mock_logger.warning.reset_mock()
    with patch('src.core.cli_controller.search_file_in_dirs', return_value='tdata-account1'):
        result = cli._validate_tag('account1')
        assert result == 'account1'
        mock_logger.warning.assert_not_called()

    mock_logger.warning.reset_mock()
    result = cli._validate_tag('default_account')
    assert result == 'default_account'
    mock_logger.warning.assert_not_called()


def test_handle_encrypt_all_tags(mock_config, mock_logger):
    """验证批量加密只处理非默认账户。"""
    from src.core.cli_controller import CLIController

    mock_config.pwd = 'test_pass'
    mock_config.tags = {
        'account1': {},
        'account2': {},
    }
    mock_config.default = 'default_account'

    cli = CLIController(
        config=mock_config,
        logger=mock_logger
    )

    mock_cipher = MagicMock()

    def cipher_factory(pwd):
        return mock_cipher

    cli._cipher_factory = cipher_factory

    with patch.object(cli, '_process_tag', return_value=(True, None)):
        with patch('src.core.cli_controller.search_file_in_dirs', return_value='tdata-test'):
            with patch('src.core.cli_controller.Path') as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.exists.return_value = True
                mock_path.return_value = mock_path_instance

                args = MagicMock()
                args.encrypt = True
                args.decrypt = False
                args.tag = None
                args.help = False
                args.version = False
                args.settings = False

                result = cli.handle_actions(args)
                assert result is True

                assert cli._process_tag.call_count == 2
                call_args = cli._process_tag.call_args_list
                assert call_args[0][0][0] != 'default_account'
                assert call_args[1][0][0] != 'default_account'


def test_handle_decrypt_all_tags(mock_config, mock_logger):
    """验证批量解密只处理非默认账户。"""
    from src.core.cli_controller import CLIController

    mock_config.pwd = 'test_pass'
    mock_config.tags = {
        'account1': {},
        'account2': {},
    }
    mock_config.default = 'default_account'

    cli = CLIController(
        config=mock_config,
        logger=mock_logger
    )

    mock_cipher = MagicMock()

    def cipher_factory(pwd):
        return mock_cipher

    cli._cipher_factory = cipher_factory

    with patch.object(cli, '_process_tag', return_value=(True, None)):
        with patch('src.core.cli_controller.search_file_in_dirs', return_value='tdata-test'):
            with patch('src.core.cli_controller.Path') as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.exists.return_value = True
                mock_path.return_value = mock_path_instance

                args = MagicMock()
                args.encrypt = False
                args.decrypt = True
                args.tag = None
                args.help = False
                args.version = False
                args.settings = False

                result = cli.handle_actions(args)
                assert result is True

                assert cli._process_tag.call_count == 2
                call_args = cli._process_tag.call_args_list
                assert call_args[0][0][0] != 'default_account'
                assert call_args[1][0][0] != 'default_account'


def test_process_tag_already_encrypted_skips(mock_config, mock_logger):
    """验证已加密账户不会被重复加密，避免密文被二次破坏。"""
    from src.core.cli_controller import CLIController

    cli = CLIController(
        config=mock_config,
        logger=mock_logger
    )

    mock_cipher = MagicMock()
    tag = 'account1'

    with patch('src.core.cli_controller.AESCipher.is_encrypted', return_value=True):
        with patch('src.core.cli_controller.search_file_in_dirs', return_value='tdata-account1'):
            with patch('src.core.cli_controller.Path') as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.exists.return_value = True
                mock_path.return_value = mock_path_instance

                success, reason = cli._process_tag(tag, 'encrypt', mock_cipher)

                assert success is False
                assert reason == '已加密'
                mock_cipher.encrypt.assert_not_called()

    mock_cipher.encrypt.reset_mock()
    with patch('src.core.cli_controller.AESCipher.is_encrypted', return_value=False):
        with patch('src.core.cli_controller.search_file_in_dirs', return_value='tdata-account1'):
            with patch('src.core.cli_controller.Path') as mock_path:
                mock_path_instance = MagicMock()
                mock_path_instance.exists.return_value = True
                mock_path.return_value = mock_path_instance

                success, reason = cli._process_tag(tag, 'encrypt', mock_cipher)

                assert success is True
                assert reason is None
                mock_cipher.encrypt.assert_called_once()
