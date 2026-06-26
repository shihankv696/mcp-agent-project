import asyncio
import logging
import sys
from server import config
from mcp.server import Server
from mcp.types import Tool, TextContent
from pathlib import Path

def is_path_allowed(target_path: str):
    for curr_dir in config.ALLOWED_DIRECTORIES:
        try:
            if target_path.is_relative_to(curr_dir):
                return True
        except ValueError:
            pass
    return False

async def file_read(file_path: str):
    if not file_path:
        return [TextContent(type="text", text="The is empty.")]

    try:
        target = Path(file_path).resolve()
    except Exception as e:
        return [TextContent(type="text", text=f"{file_path} is an Invalid file path")]
    
    if not is_path_allowed(target):
        return [TextContent(type="text", text=f"Error: Access denied to {target}.")]
    
    if not target.exists():
        return [TextContent(type="text", text=f"Error: {target} not found.")]

    if not target.is_file():
        return [TextContent(type="text", text=f"Error: {target} is not a file.")]

    
    if target.stat().st_size > config.MAX_FILE_SIZE:
        return [TextContent(type="text", text=f"Error: File too large. Max allowed: {config.MAX_FILE_SIZE} bytes.")]

    try:
        return [TextContent(type="text", text=f"content: {target.read_text()} size_bytes: {target.stat().st_size}, Path: {str(target)}")]
    except PermissionError as e:
        return [TextContent(type="text", text=f"Error: Permission denied: {e}")]

    except UnicodeDecodeError as e:
        return [TextContent(type="text", text=f"Error: File is not readable as plain text.")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]
