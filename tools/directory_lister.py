import datetime
import json
from pathlib import Path
from server import config
from mcp.types import TextContent
from server.logger import get_logger 

async def list_directory(directory_path):
    logger = get_logger(__name__) 
    logger.info(f"List_directory called with path: {directory_path}")

    if not directory_path:
        logger.warning("list_directory called with empty path")
        return [TextContent(type="text", text="Error: Path is missing or invalid. Please provide a valid file path.")]
    
    path = Path(directory_path).resolve()

    is_allowed = False
    for allowed_folder in config.ALLOWED_DIRECTORIES:
        if path.is_relative_to(Path(allowed_folder)):
            is_allowed = True
            break

    if is_allowed == False:
        logger.warning(f"Access denied. {path} is outside allowed directories.")
        return [TextContent(type="text", text=f"Error: Access denied. {path} is outside allowed directories.")]

    if not path.exists():
        logger.warning(f"Directory not found: {path}")
        return [TextContent(type="text", text=f"Error: {path} not found.")]
    
    if not path.is_dir():
        logger.warning(f"The {path} is not directory.")
        return [TextContent(type="text", text=f"Error: {path} is a file, not a directory.")]
        
    result_list = []
    for entry in path.iterdir():
        try:
            stat = entry.stat()
            size = stat.st_size
            modified = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
        except (PermissionError, OSError):
            size = None
            modified = None
        
        if entry.is_file():
            my_dict = {
                "name": entry.name,
                "type": "file",
                "size_bytes": size,
                "modified": modified
            }
            result_list.append(my_dict)
            
        elif entry.is_dir(): 
            my_dict = {
                "name": entry.name,
                "type": "directory",
                "size_bytes": None, # directories show None (content size not calculated)
                "modified": modified
            }
            result_list.append(my_dict)
    
    
    total_found = len(result_list)
    truncated = False

    if total_found > config.MAX_DIRECTORY_ENTRIES:
        result_list = result_list[:config.MAX_DIRECTORY_ENTRIES]
        truncated = True



    logger.info(f"list_directory completed: {len(result_list)} items returned for {directory_path}")
    return [TextContent(
        type="text",
        text=json.dumps({
            "success": True,
            "directory": str(path),
            "total_shown": len(result_list),
            "truncated": truncated,
            "note": f"Showing {config.MAX_DIRECTORY_ENTRIES} of {total_found} items" if truncated else None,
            "entries": result_list
        }, indent=2)
    )]