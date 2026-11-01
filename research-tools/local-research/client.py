"""Working-directory-independent remote MCP launcher."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from local_research.remote_mcp import mcp
if __name__=='__main__':mcp.run(transport='stdio')
