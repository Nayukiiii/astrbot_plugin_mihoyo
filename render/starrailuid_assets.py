from pathlib import Path


VENDOR_DIR = Path(__file__).parent / "starrailuid_vendor"


def vendor_texture(module: str, dirname: str = "texture2D") -> Path:
    return VENDOR_DIR / module / dirname


def first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None
