#!/usr/bin/env python3
"""Remove this project's build products without requiring kernel headers."""
from pathlib import Path
import shutil


def clean(root):
    patterns = ("*.o", "*.ko", "*.mod", "*.mod.c", ".*.cmd", ".*.d",
                "Module.symvers", "modules.order")
    # All Kbuild outputs for this module live in the project root or src/.
    for directory in (root, root / "src"):
        if directory.is_symlink() or not directory.is_dir():
            continue
        for pattern in patterns:
            for path in directory.glob(pattern):
                if path.is_symlink() or path.is_file():
                    path.unlink()
    temporary = root / ".tmp_versions"
    if temporary.is_symlink():
        temporary.unlink()
    elif temporary.is_dir():
        shutil.rmtree(temporary)


if __name__ == "__main__":
    clean(Path(__file__).resolve().parents[1])
