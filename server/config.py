''' 
ALGORITHM
STEP 1: START
STEP 2: Load environment variables 
STEP 3: Define server identity
STEP 4: Define timeout limits
STEP 5: Define logging preferences
STEP 6: Validate critical settings
STEP 7: STOP
'''

#import needed headers
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import sys

#Load environment variables

load_dotenv() # loads the data gets from your .env file!

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") #Never add to log or print this value

if not ANTHROPIC_API_KEY: 
    raise ValueError("ERROR: Missing required environment variable: API_KEY")

#---    SERVER IDENTITY    ---
SERVER_NAME: str = os.getenv("SERVER_NAME", "my_server")
VERSION_NUMBER: str = os.getenv("VERSION_NUMBER", "1.0.0")
DESCRIPTION: str = os.getenv("DESCRIPTION", "MCP Server for AI Agent")

#---    TIMEOUT SETTINGS    ---
TOOL_TIMEOUT: int = 20 #seconds
SESSION_TIMEOUT: int = 300 #seconds (5 minutes)

if TOOL_TIMEOUT <= 0:
    raise ValueError("TOOL_TIMEOUT must be positive")

if SESSION_TIMEOUT <= 0:
    raise ValueError("SESSION_TIMEOUT must be positive")

#---    PATH CONFIGURATION     ---
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

ALLOWED_DIRECTORIES: list[Path] =  [PROJECT_ROOT / "docs", PROJECT_ROOT / "data", PROJECT_ROOT / "resources"]

#Check wheather the allowed directories is exits or not
for directory in ALLOWED_DIRECTORIES:
    if directory.exists() and directory.is_dir():
        continue
    else:
        directory.mkdir(parents=True,exist_ok=True)
    
#---    LOGGING SETUP   ---
#logging.basicConfig(level=logging.INFO, filename="log.log", filemode="a", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("log.log")
file_handler.setLevel(logging.INFO)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)

formatter =logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

logger.info("Config loaded successfully")
logger.info(f"Server: {SERVER_NAME} version: {VERSION_NUMBER}")
logger.info(f"Project root: {PROJECT_ROOT}")
logger.info(f"Allowed dirs: {ALLOWED_DIRECTORIES}")

def get_config_summary():
    return {
        "server_name": SERVER_NAME,
        "version": VERSION,
        "tool_timeout": TOOL_TIMEOUT,
        "session_timeout": SESSION_TIMEOUT,
        "allowed_directories": [str(d) for d in ALLOWED_DIRECTORIES],
    }