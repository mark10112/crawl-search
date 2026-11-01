"""Measure real MCP startup and calls over a persistent stdio connection."""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(output, docker=False):
    start = time.perf_counter()
    launcher = Path(__file__).resolve().parents[2] / "server.py"
    parameters = StdioServerParameters(command=sys.executable, args=[str(launcher)], cwd=str(Path.home()),
                                       env={**os.environ, "PYTHONIOENCODING": "utf-8", "CRAWL4AI_NO_CLOUD_NOTICE": "1"})
    if docker:
        parameters = StdioServerParameters(command="docker", args=["run", "--rm", "-i", "local-research-stack:0.1.0"])
    results = {}
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            results["startup_initialize_ms"] = round((time.perf_counter()-start)*1000, 2)
            tools = await session.list_tools()
            results["tools"] = [tool.name for tool in tools.tools]
            calls = []
            for name, args in [
                ("research_health", {}),
                ("research_search", {"query": "Front Palace crisis 1874 1875", "limit": 3}),
                ("research_read", {"url": "https://docs.searxng.org/dev/search_api.html", "cache": False}),
                ("research_read", {"url": "https://docs.searxng.org/dev/search_api.html", "cache": True}),
                ("research_read", {"url": "https://so04.tci-thaijo.org/index.php/kjss/article/download/243645/165556", "max_pages": 1, "cache": False}),
                ("research_read", {"url": "https://docs.searxng.org/dev/search_api.html", "cache": True}),
            ]:
                clock = time.perf_counter()
                response = await session.call_tool(name, args)
                content = response.structuredContent
                if not content:
                    texts = [item.text for item in response.content if item.type == "text"]
                    try:
                        content = json.loads(texts[0])
                    except (ValueError, IndexError):
                        content = {"raw": texts}
                calls.append({"tool": name, "arguments": args, "round_trip_ms": round((time.perf_counter()-clock)*1000, 2),
                              "is_error": response.isError, "result": content})
            results["calls"] = calls
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(path.resolve()), "startup_initialize_ms": results["startup_initialize_ms"],
                      "tools": results["tools"], "calls": [{"tool": c["tool"], "round_trip_ms": c["round_trip_ms"],
                      "is_error": c["is_error"], "ok": c["result"].get("ok")} for c in results["calls"]]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/mcp-probe.json")
    parser.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.output, args.docker))
