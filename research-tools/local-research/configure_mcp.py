"""Set only this package's MCP timeout keys, preserving the rest of Codex config."""
import re
import tomllib
from pathlib import Path

target = Path.home() / ".codex" / "config.toml"
text = target.read_text(encoding="utf-8")
before = tomllib.loads(text)
assert "local-research" in before.get("mcp_servers", {}), "Register local-research first"
pattern = re.compile(r"(?m)^\[mcp_servers\.local-research\]\s*$")
match = pattern.search(text)
assert match, "Expected a plain local-research section"
end_match = re.search(r"(?m)^\[", text[match.end():])
end = match.end() + end_match.start() if end_match else len(text)
section = text[match.end():end]
for key, value in [("startup_timeout_sec", 30), ("tool_timeout_sec", 240)]:
    line = re.compile(rf"(?m)^{key}\s*=.*$")
    if line.search(section):
        section = line.sub(f"{key} = {value}", section)
    else:
        section = "\n" + f"{key} = {value}" + section
updated = text[:match.end()] + section.rstrip() + "\n\n" + text[end:]
after = tomllib.loads(updated)
expected = before.copy()
expected["mcp_servers"] = dict(before["mcp_servers"])
expected["mcp_servers"]["local-research"] = {**before["mcp_servers"]["local-research"],
                                            "startup_timeout_sec": 30, "tool_timeout_sec": 240}
assert after == expected, "Unexpected config change; refusing write"
temporary = target.with_name("config.toml.local-research.tmp")
temporary.write_text(updated, encoding="utf-8")
temporary.replace(target)
print("Only local-research startup/tool timeouts updated: 30s / 240s")
