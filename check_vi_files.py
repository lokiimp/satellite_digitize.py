from pathlib import Path
import argparse


def find_vi_files(base_dir: Path):
    """Yield *.vi.json files from date subdirectories in sorted order."""
    for date_dir in sorted(base_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        # search within this date directory recursively
        for path in sorted(date_dir.rglob("*.vi.json")):
            if path.is_file():
                yield path


def contains_target_strings(text: str) -> bool:
    """Return True if text contains the target strings."""
    lower = text.lower()
    return "5n" in lower or "sn" in lower


def main(directory: str):
    base_dir = Path(directory)
    if not base_dir.exists():
        print(f"Directory {directory} does not exist")
        return
    for vi_file in find_vi_files(base_dir):
        try:
            content = vi_file.read_text(errors="ignore")
            if contains_target_strings(content):
                print(vi_file)
        except Exception as e:
            print(f"Error reading {vi_file}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check .vi.json files for 5N or SN")
    parser.add_argument(
        "directory",
        nargs="?",
        default="/ships22/sds/goes/digitized/32A/vissr/1977",
        help="Base directory containing date folders",
    )
    args = parser.parse_args()
    main(args.directory)
