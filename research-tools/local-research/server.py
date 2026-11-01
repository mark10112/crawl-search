"""Portable absolute-path MCP launcher, independent of client working directory."""
import os
from pathlib import Path

root = Path(__file__).resolve().parent
os.environ.setdefault("LOCAL_RESEARCH_STATE", str(root / ".cache" / "reader"))
os.environ.setdefault("LOCAL_RESEARCH_TESSDATA", str(root / ".cache" / "tessdata"))
os.environ.setdefault("CRAWL4AI_NO_CLOUD_NOTICE", "1")

from local_research.mcp_server import main

if __name__ == "__main__":
    main()
