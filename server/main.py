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

import config
import asyncio
import logging
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pathlib import Path


# ── Logging Setup (ONE place only) ───────────
def setup_logging():
    logger = logging.getLogger()         # root logger
    logger.setLevel(logging.INFO)

    # File handler → uses LOG_FILE from config
    file_handler = logging.FileHandler(config.LOG_FILE)
    file_handler.setLevel(logging.INFO)

    # stderr handler → safe for MCP (not stdout)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    stderr_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)

    return logging.getLogger(__name__)


# Setup logging FIRST before anything else
logger = setup_logging()

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
        Tool(
            name="file_read",
            description="Reads and returns the complete text content of a file from the local filesystem. Use this when you need to read any text file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The full path to the file to read"
                    }
                },
                "required": ["path"]
            }
        )
    ]


# ── Tool Execution ────────────────────────────
@mcp.call_tool()
async def handle_call_tools(name: str, arguments: dict):
    logger.info(f"Tool called: {name}")
    logger.info(f"Arguments received: {arguments}")

    if name == "file_read":
        path_string = arguments.get("path")

        if not path_string:
            return [TextContent(type="text", text="Error: Missing required argument 'path'.")]

        try:
            # Resolve to absolute path (no try/except needed here)
            path = Path(path_string).resolve()

            # Security check
            is_allowed = any(
                Path(allowed_dir).resolve() in path.parents
                for allowed_dir in config.ALLOWED_DIRECTORIES
            )

            if not is_allowed:
                logger.warning(f"Access denied for path: {path}")
                return [TextContent(type="text", text=f"Error: Access denied: {path} is outside allowed directories")]

            # Existence check
            if not path.exists():
                logger.info(f"File does not exist: {path}")
                return [TextContent(type="text", text=f"Error: File does not exist: {path}")]

            # File type check
            if not path.is_file():
                return [TextContent(type="text", text=f"Error: {path} is not a file.")]

            # Size check
            if path.stat().st_size > config.MAX_FILE_SIZE:
                logger.info(f"File too large: {path}")
                return [TextContent(type="text", text=f"Error: File too large. Max allowed: {config.MAX_FILE_SIZE} bytes.")]

            # Read file
            with open(path, 'r', encoding="utf-8") as f:
                content = f.read()

            logger.info(f"File successfully read: {path}")
            return [TextContent(type="text", text=content)]

        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            return [TextContent(type="text", text=f"Error: Permission denied: {e}")]

        except UnicodeDecodeError as e:
            logger.error(f"Cannot read as text: {e}")
            return [TextContent(type="text", text=f"Error: File is not readable as plain text.")]

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {e}")]

    else:
        logger.warning(f"Unknown tool: {name}")
        return [TextContent(type="text", text=f"Error: Tool '{name}' is not supported.")]


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