from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.vectorize_tools import vectorize_tools


def main() -> None:
    chroma_dir = Path("data/chroma_db")
    sqlite_file = chroma_dir / "chroma.sqlite3"
    if sqlite_file.exists():
        print("Chroma index already exists. Skipping tool vectorization.")
        return

    chroma_dir.mkdir(parents=True, exist_ok=True)
    print("Building Chroma tool index ...")
    vectorize_tools()
    print("Chroma tool index complete.")


if __name__ == "__main__":
    main()
