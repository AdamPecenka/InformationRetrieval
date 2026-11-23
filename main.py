import argparse
import sys
from constants.extractor import ATHLETES_TSV_PATH, RESULTS_TSV_PATH
from constants.join import WIKI_JOIN_PATH
from constants.lucene import (
    LUCENE_BM25_B,
    LUCENE_BM25_K1,
    LUCENE_COMPARISON_REPEATS,
    LUCENE_DOCS_PATH,
    LUCENE_INDEX_DIR,
)
from constants.wiki import (
    WIKI_DUMP_PATH,
    WIKI_FULL_PAGES_PATH,
    WIKI_PAGES_PATH,
    WIKI_PEOPLE_PATH,
    WIKI_RELEVANT_PATH,
    WIKI_SAMPLES_DIR,
    WIKI_SLICE_PAGES,
    WIKI_SLICE_PATH,
)

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
    wiki_slice.add_argument("--input", default=WIKI_DUMP_PATH, help="the dump (.xml.bz2 or .xml)")
    wiki_slice.add_argument("--output", default=WIKI_SLICE_PATH)
    wiki_slice.add_argument("--pages", type=int, default=WIKI_SLICE_PAGES)

    wiki_parse = subparsers.add_parser("wiki-parse",
                                       help="wikipedia XML -> parquet with Spark (articles only, redirects dropped)")
    wiki_parse.add_argument("--input", default=WIKI_SLICE_PATH,
                            help="slice or full dump (default: the slice)")
    wiki_parse.add_argument("--output", default=WIKI_PAGES_PATH)
    wiki_parse.add_argument("--bio-only", action="store_true", help="keep only pages with birth data")

    wiki_filter = subparsers.add_parser("wiki-filter", help="full articles parquet -> persons and Olympic pages")
    wiki_filter.add_argument("--input", default=WIKI_FULL_PAGES_PATH)
    wiki_filter.add_argument("--output", default=WIKI_RELEVANT_PATH)

    wiki_audit = subparsers.add_parser("wiki-audit", help="check the filter against Olympedia athlete names")
    wiki_audit.add_argument("--athletes", default=ATHLETES_TSV_PATH)
    wiki_audit.add_argument("--pages", default=WIKI_FULL_PAGES_PATH)
    wiki_audit.add_argument("--relevant", default=WIKI_RELEVANT_PATH)

    wiki_sample = subparsers.add_parser("wiki-sample", help="write the wikitext of chosen articles to text files")
    wiki_sample.add_argument("--input", default=WIKI_RELEVANT_PATH)
    wiki_sample.add_argument("--output", default=WIKI_SAMPLES_DIR)
    wiki_sample.add_argument("--titles", nargs="+", required=True, help="exact article titles")
    wiki_sample.add_argument("--head", type=int, default=8000, help="characters kept from the start")
    wiki_sample.add_argument("--tail", type=int, default=6000, help="characters kept from the end")

    wiki_extract = subparsers.add_parser(
        "wiki-extract",
        help="relevant pages parquet -> parquet of persons with regex-extracted attributes (stage 3)",
    )
    wiki_extract.add_argument("--input", default=WIKI_RELEVANT_PATH)
    wiki_extract.add_argument("--output", default=WIKI_PEOPLE_PATH)

    wiki_join = subparsers.add_parser(
        "wiki-join",
        help="join Olympedia athletes with wikipedia people: exact id, name + birth date, name + birth year (stage 4)",
    )
    wiki_join.add_argument("--people", default=WIKI_PEOPLE_PATH)
    wiki_join.add_argument("--athletes", default=ATHLETES_TSV_PATH)
    wiki_join.add_argument("--output", default=WIKI_JOIN_PATH)

    extract_spark = subparsers.add_parser(
        "extract-spark",
        help="same extraction as `extract`, run with Spark (no resume); writes parquet and TSVs",
    )
    extract_spark.add_argument(
        "--verify",
        action="store_true",
        help="parse every page again with the plain extractor and compare both outputs",
    )

    lucene_export = subparsers.add_parser(
        "lucene-export",
        help="Spark: athletes + results + best Wikipedia page of the join -> one TSV row per athlete for the Lucene index",
    )
    lucene_export.add_argument("--athletes", default=ATHLETES_TSV_PATH)
    lucene_export.add_argument("--results", default=RESULTS_TSV_PATH)
    lucene_export.add_argument("--joined", default=WIKI_JOIN_PATH)
    lucene_export.add_argument("--output", default=LUCENE_DOCS_PATH)

    lucene_index = subparsers.add_parser(
        "lucene-index",
        help="PyLucene (run in the container): data/lucene/docs.tsv -> Lucene index, always rebuilt from scratch",
    )
    lucene_index.add_argument("--docs", default=LUCENE_DOCS_PATH)
    lucene_index.add_argument("--index", default=LUCENE_INDEX_DIR)

    lucene_search = subparsers.add_parser(
        "lucene-search",
        help="PyLucene (run in the container): search the Lucene index, e.g. lucene-search \"sport:swimming born_year:[1980 TO 1989]\"",
    )
    lucene_search.add_argument("query", nargs="+", help="Lucene query string (words, field:word, \"phrase\", AND/OR/NOT, word~1, field:[a TO b])")
    lucene_search.add_argument("--top", type=int, default=10, help="number of results (default: 10)")
    lucene_search.add_argument(
        "--mode",
        choices=["and", "or"],
        default="and",
        help="operator between bare words: and = every word must match (default), or = any word",
    )
    lucene_search.add_argument(
        "--similarity",
        choices=["bm25", "classic"],
        default="bm25",
        help="bm25 (default) or classic = Lucene's tf-idf (ClassicSimilarity)",
    )
    lucene_search.add_argument("--k1", type=float, default=LUCENE_BM25_K1, help="BM25 k1")
    lucene_search.add_argument("--b", type=float, default=LUCENE_BM25_B, help="BM25 b")
    lucene_search.add_argument(
        "--sport-medal",
        action="append",
        default=[],
        help="athletes with this medal in this sport, e.g. aquatics:gold (repeatable, all must hold)",
    )
    lucene_search.add_argument(
        "--discipline-medal",
        action="append",
        default=[],
        help="athletes with this medal in this discipline, e.g. swimming:gold (repeatable, all must hold)",
    )
    lucene_search.add_argument("--index", default=LUCENE_INDEX_DIR)

    lucene_compare = subparsers.add_parser(
        "lucene-compare",
        help="PyLucene (run in the container): own index vs Lucene index on the test queries, precision / recall / rank / latency",
    )
    lucene_compare.add_argument("--docs", default=LUCENE_DOCS_PATH)
    lucene_compare.add_argument("--index", default=LUCENE_INDEX_DIR)
    lucene_compare.add_argument("--repeats", type=int, default=LUCENE_COMPARISON_REPEATS, help="runs per query for the latency mean")

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

    if args.command == "lucene-export":
        from indexer.lucene_export import run_lucene_export
        return run_lucene_export(args.athletes, args.results, args.joined, args.output)

    if args.command == "lucene-index":
        from indexer.lucene_builder import run_lucene_indexer
        return run_lucene_indexer(args.docs, args.index)

    if args.command == "lucene-search":
        from indexer.lucene_search import run_lucene_search
        return run_lucene_search(
            " ".join(args.query), args.top, args.mode == "and", args.similarity, args.k1, args.b,
            args.sport_medal, args.discipline_medal, args.index,
        )

    if args.command == "lucene-compare":
        from indexer.lucene_compare import run_lucene_compare
        return run_lucene_compare(args.docs, args.index, args.repeats)

    return 1

if __name__ == "__main__":
    sys.exit(main())