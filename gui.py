"""Stable graphical entry point; the application and dialogs are Qt Quick."""
from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    from qml_app import main as qml_main

    return qml_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
