import argparse
import sys

def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="VINF Olympedia search project")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser(
        "crawl",
        help="download pages; runs until the frontier is empty (Ctrl-C to stop, rerun to resume)",
    )
    crawl.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="optional cap on fetches in this run (default: no limit)",
    )
    extract = subparsers.add_parser(
        "extract",
        help="parse the stored athlete pages into data/extracted/athletes.tsv and results.tsv (resumes by default)",
    )
    extract.add_argument(
        "--rebuild",
        action="store_true",
        help="drop the existing TSVs and extract every page again",
    )

    return parser

def main() -> int:
    configure_console()
    args = build_parser().parse_args()

    if args.command == "crawl":
        from crawler.engine import run_crawler
        return run_crawler(max_pages=args.max_pages)

    if args.command == "extract":
        from extractor.engine import run_extractor
        return run_extractor(rebuild=args.rebuild)

    return 1

if __name__ == "__main__":
    sys.exit(main())