import argparse
import asyncio
import json

from .stack import ResearchStack


async def run(args):
    stack = ResearchStack()
    try:
        if args.command == "health":
            return await stack.health()
        if args.command == "search":
            return await stack.search(args.query, args.limit)
        return await stack.read(args.url, mode=args.mode, max_pages=args.pages, cache=not args.no_cache,
                                ocr_engine=args.ocr_engine,language_hint=args.language,ocr_policy=args.policy)
    finally:
        await stack.close()


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    read = sub.add_parser("read")
    read.add_argument("url")
    read.add_argument("--mode", choices=["auto", "basic", "browser", "ocr"], default="auto")
    read.add_argument("--pages", type=int, default=5)
    read.add_argument("--no-cache", action="store_true")
    read.add_argument("--ocr-engine", choices=["auto", "tesseract", "docling",'router'], default="auto")
    read.add_argument('--language',default=None)
    read.add_argument('--policy',choices=['balanced','quality'],default='balanced')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
