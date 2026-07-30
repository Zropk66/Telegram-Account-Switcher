"""打包脚本."""

import subprocess
import sys
import time

from main import VERSION

TOOLCHAIN = ["mingw64", "msvc"][1]
BUILD_MODE = ["release", "preview", "debug"][0]


def build_args(build_mode: str, toolchain: str) -> list[str]:
    """构建参数."""
    args = []

    if toolchain == "mingw64":
        args.append("--mingw64")
    elif toolchain == "msvc":
        args.append("--msvc=latest")
    else:
        raise ValueError(f"Unsupported TOOLCHAIN: {toolchain}")

    common_args = [
        "--onefile",
        "--plugin-enable=pyside6",
        f"--output-filename=TAS_{build_mode}_{toolchain}_v{VERSION}",
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
    if isinstance(BUILD_MODE, list):
        for mode in BUILD_MODE:
            run_build(mode, TOOLCHAIN)
    else:
        run_build(BUILD_MODE, TOOLCHAIN)

    return 0


if __name__ == "__main__":
    sys.exit(main())
