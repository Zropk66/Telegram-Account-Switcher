"""打包脚本."""

import argparse
import platform
import subprocess
import sys
import time

from src.core.constants import APP_VERSION as VERSION

TOOLCHAIN = ["msvc", "mingw64"][0]
BUILD_MODE = ["release", "preview", "debug"][0]


def parse_args() -> argparse.Namespace:
    """解析命令行参数."""
    parser = argparse.ArgumentParser(description="TAS Build Script")
    parser.add_argument(
        "--mode",
        "-m",
        choices=["release", "preview", "debug"],
        default=BUILD_MODE,
        help="指定构建模式 (release/preview/debug)",
    )
    parser.add_argument(
        "--toolchain",
        "-t",
        choices=["msvc", "mingw64"],
        default=TOOLCHAIN,
        help="指定工具链 (msvc/mingw64)",
    )
    return parser.parse_args()


def build_args(build_mode: str, toolchain: str) -> list[str]:
    """构建参数."""
    args = []

    if toolchain == "mingw64":
        args.append("--mingw64")
    elif toolchain == "msvc":
        args.append("--msvc=latest")
    else:
        raise ValueError(f"Unsupported TOOLCHAIN: {toolchain}")

    py_ver = platform.python_version()
    os_name = "Windows" if sys.platform == "win32" else sys.platform.capitalize()
    arch = "x64" if sys.maxsize > 2**32 else "x86"
    toolchain_upper = toolchain.upper()

    output_filename = f"TAS_v{VERSION}_{os_name}_{arch}_Py{py_ver}_{toolchain_upper}.exe"

    common_args = [
        "--onefile",
        "--assume-yes-for-downloads",
        "--plugin-enable=pyside6",
        "--include-data-files=src/hook/hook.dll=src/hook/hook.dll",
        f"--output-filename={output_filename}",
        "--output-dir=output",
        "--show-progress",
        "--jobs=8",
        "--windows-company-name=Company",
        "--windows-product-name=TAS",
        f"--windows-product-version={VERSION}",
        f"--windows-file-version={VERSION}",
        "--windows-file-description=Telegram Account Switcher",
    ]
    args.extend(common_args)
    if build_mode == "debug":
        args.extend(["--show-memory"])
    elif build_mode == "preview":
        args.extend(["--deployment", "--remove-output", "--lto=yes"])
    elif build_mode == "release":
        args.extend(["--windows-console-mode=disable", "--deployment", "--remove-output", "--lto=yes"])
    else:
        raise ValueError(f"Unsupported BUILD_MODE: {build_mode}")
    args.append(".\\launcher.py")
    return args


def run_build(build_mode: str, toolchain: str) -> int:
    """运行构建命令."""
    print(f"Build mode: {build_mode}")
    print(f"Toolchain: {toolchain}")

    args = build_args(build_mode, toolchain)
    command = ["nuitka"] + args
    print("Command:")
    print(" ".join(command))
    start_time = time.time()
    subprocess.run(command, shell=True, check=True)
    print(f"\nBuild finished in {time.time() - start_time:.2f} seconds")

    return 0


def main() -> int:
    """主函数."""
    args = parse_args()
    return run_build(args.mode, args.toolchain)


if __name__ == "__main__":
    sys.exit(main())
