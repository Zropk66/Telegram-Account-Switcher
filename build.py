"""用 Nuitka 把 TAS 打包成单个可执行文件。"""
import subprocess
import sys
import time

from main import VERSION

TOOLCHAIN = ["mingw64", "msvc"][0]
BUILD_MODE = ["release", "debug"][0]


def build_args() -> list[str]:
    args = []

    if TOOLCHAIN == "mingw64":
        args.append("--mingw64")
    elif TOOLCHAIN == "msvc":
        args.append("--msvc=latest")
    else:
        raise ValueError(f"Unsupported TOOLCHAIN: {TOOLCHAIN}")

    common_args = [
        "--standalone",
        "--plugin-enable=pyside6",
        f"--output-filename=TAS_{BUILD_MODE}_{TOOLCHAIN}_v{VERSION}",
        "--output-dir=output",
        "--show-progress",
        "--jobs=8",
    ]
    args.extend(common_args)

    if BUILD_MODE == "release":
        args.extend([
            "--windows-console-mode=disable",
            "--onefile",
            "--remove-output",
            "--lto=yes"
        ])
    elif BUILD_MODE == "debug":
        args.extend("--show-memory")
    else:
        raise ValueError(f"Unsupported BUILD_MODE: {BUILD_MODE}")
    args.append(".\\launcher.py")
    return args


def main() -> int:
    print(f"Build mode: {BUILD_MODE}")
    print(f"Toolchain: {TOOLCHAIN}")

    args = build_args()
    command = ["nuitka"] + args
    print("Command:")
    print(" ".join(command))
    start_time = time.time()
    subprocess.run(command, shell=True, check=True)
    print(f"\nBuild finished in {time.time() - start_time:.2f} seconds")

    return 1


if __name__ == "__main__":
    sys.exit(main())
