import argparse
import sys
import constants

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

    subparsers.add_parser(
        "index",
        help="build the inverted index from data/extracted/athletes.tsv into data/index/ (always rebuilt from scratch)",
    )
    search = subparsers.add_parser(
        "search",
        help="rank athletes for a query with the index",
    )
    search.add_argument("query", nargs="+", help="query words")
    search.add_argument("--top", type=int, default=10, help="number of results per ranking (default: 10)")
    search.add_argument(
        "--rank",
        choices=["idf", "prob", "bm25", "all"],
        default="all",
        help="ranking: idf = tf-idf with log(N/df), prob = tf-idf with probabilistic idf, bm25, all = print every ranking (default)",
    )
    search.add_argument(
        "--mode",
        choices=["and", "or"],
        default="and",
        help="and = only athletes that contain every query word (default), or = athletes that contain any of the words",
    )

    wiki_slice = subparsers.add_parser("wiki-slice",
                                       help="copy the first pages of the wikipedia dump into a small XML file (development)")
    wiki_slice.add_argument("--input", default=constants.WIKI_DUMP_PATH, help="the dump (.xml.bz2 or .xml)")
    wiki_slice.add_argument("--output", default=constants.WIKI_SLICE_PATH)
    wiki_slice.add_argument("--pages", type=int, default=constants.WIKI_SLICE_PAGES)

    wiki_parse = subparsers.add_parser("wiki-parse",
                                       help="wikipedia XML -> parquet with Spark (articles only, redirects dropped)")
    wiki_parse.add_argument("--input", default=constants.WIKI_SLICE_PATH,
                            help="slice or full dump (default: the slice)")
    wiki_parse.add_argument("--output", default=constants.WIKI_PAGES_PATH)
    wiki_parse.add_argument("--bio-only", action="store_true", help="keep only pages with birth data")

    wiki_filter = subparsers.add_parser("wiki-filter", help="full articles parquet -> persons and Olympic pages")
    wiki_filter.add_argument("--input", default=constants.WIKI_FULL_PAGES_PATH)
    wiki_filter.add_argument("--output", default=constants.WIKI_RELEVANT_PATH)

    wiki_audit = subparsers.add_parser("wiki-audit", help="check the filter against Olympedia athlete names")
    wiki_audit.add_argument("--athletes", default=constants.WIKI_AUDIT_ATHLETES_PATH)
    wiki_audit.add_argument("--pages", default=constants.WIKI_FULL_PAGES_PATH)
    wiki_audit.add_argument("--relevant", default=constants.WIKI_RELEVANT_PATH)

    wiki_sample = subparsers.add_parser("wiki-sample", help="write the wikitext of chosen articles to text files")
    wiki_sample.add_argument("--input", default=constants.WIKI_RELEVANT_PATH)
    wiki_sample.add_argument("--output", default=constants.WIKI_SAMPLES_DIR)
    wiki_sample.add_argument("--titles", nargs="+", required=True, help="exact article titles")
    wiki_sample.add_argument("--head", type=int, default=8000, help="characters kept from the start")
    wiki_sample.add_argument("--tail", type=int, default=6000, help="characters kept from the end")

    wiki_extract = subparsers.add_parser(
        "wiki-extract",
        help="relevant pages parquet -> parquet of persons with regex-extracted attributes (stage 3)",
    )
    wiki_extract.add_argument("--input", default=constants.WIKI_RELEVANT_PATH)
    wiki_extract.add_argument("--output", default=constants.WIKI_PEOPLE_PATH)

    wiki_join = subparsers.add_parser(
        "wiki-join",
        help="join Olympedia athletes with wikipedia people: exact id, name + birth date, name + birth year (stage 4)",
    )
    wiki_join.add_argument("--people", default=constants.WIKI_PEOPLE_PATH)
    wiki_join.add_argument("--athletes", default=constants.WIKI_AUDIT_ATHLETES_PATH)
    wiki_join.add_argument("--output", default=constants.WIKI_JOIN_PATH)

    extract_spark = subparsers.add_parser(
        "extract-spark",
        help="same extraction as `extract`, run with Spark (no resume); writes parquet and TSVs",
    )
    extract_spark.add_argument(
        "--verify",
        action="store_true",
        help="parse every page again with the plain extractor and compare both outputs",
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
    if args.command == "index":
        from indexer.engine import run_indexer
        return run_indexer()

    if args.command == "search":
        from indexer.engine import run_search
        return run_search(" ".join(args.query), top_k=args.top, method=args.rank, require_all=args.mode == "and")

    if args.command == "wiki-slice":
        from wiki.slice import run_slice
        return run_slice(args.input, args.output, args.pages)

    if args.command == "wiki-parse":
        from wiki.dump import run_parse
        return run_parse(args.input, args.output, args.bio_only)

    if args.command == "wiki-filter":
        from wiki.relevance import run_filter
        return run_filter(args.input, args.output)

    if args.command == "wiki-audit":
        from wiki.audit import run_audit
        return run_audit(args.athletes, args.pages, args.relevant)

    if args.command == "wiki-sample":
        from wiki.sample import run_sample
        return run_sample(args.input, args.output, args.titles, args.head, args.tail)

    if args.command == "wiki-extract":
        from wiki.extract import run_extract
        return run_extract(args.input, args.output)

    if args.command == "wiki-join":
        from wiki.join import run_join
        return run_join(args.people, args.athletes, args.output)

    if args.command == "extract-spark":
        from extractor.spark_job import run_spark_extractor
        return run_spark_extractor(run_verify=args.verify)

    return 1

if __name__ == "__main__":
    sys.exit(main())