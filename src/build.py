import sys

import PyInstaller.__main__


def main() -> None:
    args = (
        sys.argv[1:]
        if len(sys.argv) > 1
        else [
            "--noconfirm",
            "--onedir",
            "--windowed",
            "src/main.py",
            "--name",
            "py-agent-audit",
        ]
    )
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
