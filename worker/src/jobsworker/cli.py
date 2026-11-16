from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import db, pipeline
from .config import Settings
from .tagger import make_tagger
from .taxonomy import load_taxonomy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobsworker")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="upsert sources.yaml into the sources table")
    p_run = sub.add_parser("run", help="full ingest: fetch, filter, upsert, dedupe, tag")
    p_run.add_argument("--no-tag", action="store_true", help="skip the tagging step")
    p_run.add_argument("--source", action="append", help="only this source key (repeatable)")
    p_tag = sub.add_parser("tag", help="tag untagged active jobs without fetching")
    p_tag.add_argument("--limit", type=int)
    sub.add_parser("stats", help="print job counts")
    p_probe = sub.add_parser("probe", help="check candidate boards for India fresher posts")
    p_probe.add_argument("file", type=Path)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # request URLs can carry API keys
    settings = Settings.from_env()

    if args.cmd == "probe":
        from .probe import probe

        probe(args.file, settings)
        return 0

    with db.connect(settings.database_url) as conn:
        if args.cmd == "seed":
            n = db.seed_sources(conn, pipeline.load_sources_file(settings))
            print(f"seeded {n} sources")
        elif args.cmd == "run":
            result = pipeline.run(
                settings, conn, do_tag=not args.no_tag,
                only=set(args.source) if args.source else None,
            )
            print(json.dumps(result, default=str, indent=2))
            # Fail the scheduled job only if nothing at all could be fetched.
            if result["fetched"] == 0 and result["errors"]:
                return 1
        elif args.cmd == "tag":
            taxonomy = load_taxonomy(settings.taxonomy_path)
            tagged, cost, errors = pipeline.tag_pending(
                conn, make_tagger(settings, taxonomy), settings, args.limit
            )
            print(json.dumps({"tagged": tagged, "llm_cost_usd": cost, "errors": errors}, indent=2))
        elif args.cmd == "stats":
            print(json.dumps(db.stats(conn), default=str, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
