'''
ALGORITHM
STEP 1: Start
STEP 2: Server Initialization
STEP 3: Logging setup
STEP 4: Register list_tools handler
STEP 5: Register call_tool handler
STEP 6: MAIN entry point
STEP 7: Run the server
STEP 8: STOP
'''

import asyncio
import logging
import sys
import os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp.server import Server
from mcp import types
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pathlib import Path
from tools.file_reader import file_read
from server import config
from tools import directory_lister
from server.logger import get_logger


logger = get_logger(__name__) 

# Now safe to log - happens after MCP transport ready
# DO NOT log anything here at module level

# ── Server Initialization ─────────────────────
mcp = Server(
    config.SERVER_NAME,
    version=config.VERSION_NUMBER,
    instructions=config.INSTRUCTIONS
)


# ── Tool Registration ─────────────────────────
@mcp.list_tools()
async def handle_list_tools():
    logger.info("Tool list requested")
    return [
        types.Tool(
            name="file_read",
            description=(
                "Reads the contents of a text file from the file system. "
                "Use this when you need to see what is inside a file. "
                "Only works on text-based files within allowed directories."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read"
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="list_directory",
            description=(
                "Lists all files and subdirectories within a given"
                "directory. Returns name, type, size, and last modified"
                "date for each item. Use this before reading files to"
                "discover what files exist in a folder."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "The path to the directory you want to list"
                    }
                },
                "required": ["directory_path"]
            }
        )
    ]


# ── Tool Execution ────────────────────────────
@mcp.call_tool()
async def handle_call_tools(name: str, arguments: dict):
    logger.info(f"Tool called: {name}")
    logger.info(f"Arguments received: {arguments}")

    if name == "file_read":
        result = await file_read(arguments.get("file_path", ""))
        return [types.TextContent(type="text", text=str(result))]

    elif name == "list_directory":
        result = await directory_lister.list_directory(arguments.get("directory_path", "")) 
        return [types.TextContent(type="text", text=str(result))]
    
    else:
        logger.warning(f"Unknown tool: {name}")
        return [TextContent(type="text", text=f"Error: Tool '{name}' is Unkown.")]


# ── Main Entry Point ──────────────────────────
async def main():
    logger.info(f"Starting {config.SERVER_NAME} v{config.VERSION_NUMBER}")
    logger.info(f"Allowed directories: {config.ALLOWED_DIRECTORIES}")

    async with stdio_server() as (read_stream, write_stream):
        logger.info("stdio streams ready — waiting for connections")
        init_options = mcp.create_initialization_options()
        await mcp.run(
            read_stream,
            write_stream,
            init_options
        )

    logger.info("Server shutting down cleanly")


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        try:
            logger.info("Shutdown requested (Ctrl+C). Exiting gracefully.")
        except Exception:
            pass

    except Exception as e:
        try:
            logger.error(f"Unexpected error: {e}", exc_info=True)
        except Exception:
            pass
        sys.exit(1)     # only on real errors, not Ctrl+C