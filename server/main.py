"""
server/main.py — MCP Server Entry Point

ALGORITHM:
STEP 1: Import all dependencies
STEP 2: Initialize MCP server instance
STEP 3: Setup logging
STEP 4: Register list_tools handler (what tools exist)
STEP 5: Register call_tool handler (execute a tool)
STEP 6: Main entry point — start stdio server
STEP 7: Run until stopped
STEP 8: Shutdown cleanly
"""

import asyncio
import logging
import sys
import os

# ── Path Setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from mcp.server        import Server
from mcp.server.stdio  import stdio_server
from mcp.types         import Tool, TextContent
from server            import config
from server.logger     import get_logger
from tools.file_reader   import file_read
from tools.directory_lister import list_directory
from tools.file_searcher import search_files, initialize_search_tool

# ── Logger Setup ──────────────────────────────────────────────────────────────
logger = get_logger(__name__)

# ── Server Initialization ─────────────────────────────────────────────────────
mcp = Server(
    config.SERVER_NAME,
    version=config.VERSION_NUMBER,
    instructions=config.INSTRUCTIONS,
)


# ── Tool Registration ─────────────────────────────────────────────────────────
@mcp.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    Called by MCP clients (Claude, Inspector) to discover
    what tools this server offers.
    """
    logger.info("Tool list requested by client")

    return [
        # ── Tool 1: file_read ─────────────────────────────────────────────
        Tool(
            name="file_read",
            description=(
                "Reads the full contents of a text file from the file system. "
                "Use this when you need to see what is inside a specific file. "
                "Only works on text-based files within allowed directories. "
                "Returns the file content as a string."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "The path to the file to read. "
                            "Can be relative or absolute within allowed directories."
                        ),
                    }
                },
                "required": ["file_path"],
            },
        ),

        # ── Tool 2: list_directory ────────────────────────────────────────
        Tool(
            name="list_directory",
            description=(
                "Lists all files and subdirectories inside a given directory. "
                "Returns name, type (file or directory), size in bytes, and "
                "last modified date for each item. "
                "Use this before reading files to discover what exists in a folder."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": (
                            "The path to the directory to list. "
                            "Must be within allowed directories."
                        ),
                    }
                },
                "required": ["directory_path"],
            },
        ),

        # ── Tool 3: search_files ──────────────────────────────────────────
        Tool(
            name="search_files",
            description=(
                "Searches for files whose names contain the search query. "
                "Case-insensitive partial match on filenames. "
                "Recursively searches all subdirectories. "
                "Use this when you need to find a file but do not know its exact path. "
                "Returns a list of matching relative file paths."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "search_query": {
                        "type": "string",
                        "description": (
                            "Text to search for in file names. "
                            "Minimum 2 characters. Case-insensitive."
                        ),
                    },
                    "directory_path": {
                        "type": "string",
                        "description": (
                            "Directory to search within. "
                            "Leave empty to search the default allowed directory."
                        ),
                    },
                },
                "required": ["search_query"],
            },
        ),
    ]


# ── Tool Execution ─────────────────────────────────────────────────────────────
@mcp.call_tool()
async def handle_call_tools(name: str, arguments: dict) -> list[TextContent]:
    """
    Called by MCP clients to execute a specific tool.
    Routes to the correct tool function based on name.
    Always returns list[TextContent] — never raises to the client.
    """
    logger.info("Tool called: %s", name)
    logger.info("Arguments: %s", arguments)

    # ── Route: file_read ──────────────────────────────────────────────────
    if name == "file_read":
        file_path = arguments.get("file_path", "")
        # file_read already returns list[TextContent] — return directly
        return await file_read(file_path)

    # ── Route: list_directory ─────────────────────────────────────────────
    elif name == "list_directory":
        directory_path = arguments.get("directory_path", "")
        # list_directory already returns list[TextContent] — return directly
        return await list_directory(directory_path)

    # ── Route: search_files ───────────────────────────────────────────────
    elif name == "search_files":
        search_query   = arguments.get("search_query", "")
        directory_path = arguments.get("directory_path", "")
        # search_files already returns list[TextContent] — return directly
        return await search_files(search_query, directory_path)

    # ── Unknown Tool ──────────────────────────────────────────────────────
    else:
        logger.warning("Unknown tool requested: %s", name)
        return [TextContent(
            type="text",
            text=f"Error: Tool '{name}' is not registered on this server."
        )]


# ── Main Entry Point ───────────────────────────────────────────────────────────
async def main() -> None:
    """
    Starts the MCP server using stdio transport.
    Validates all tool configurations before accepting connections.
    """
    # Validate and initialize all tool configurations at startup
    # This catches config errors before any client connects
    try:
        initialize_search_tool()
        logger.info("search_files tool initialized successfully")
    except RuntimeError as e:
        logger.error("Tool initialization failed: %s", e)
        sys.exit(1)

    logger.info("Starting %s v%s", config.SERVER_NAME, config.VERSION_NUMBER)
    logger.info("Allowed directories: %s", config.ALLOWED_DIRECTORIES)

    async with stdio_server() as (read_stream, write_stream):
        logger.info("stdio streams ready — waiting for client connection")
        init_options = mcp.create_initialization_options()
        await mcp.run(
            read_stream,
            write_stream,
            init_options,
        )

    logger.info("Server shutting down cleanly")


# ── Entry Guard ────────────────────────────────────────────────────────────────
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
            logger.error("Unexpected server error: %s", e, exc_info=True)
        except Exception:
            pass
        sys.exit(1)