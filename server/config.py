'''
ALGORITHM
STEP 1: START
STEP 2: Load environment variables
STEP 3: Define server identity
STEP 4: Define timeout limits
STEP 5: Define path configuration
STEP 6: Validate critical settings
STEP 7: STOP
'''

from dotenv import load_dotenv
from pathlib import Path
import os

# Load environment variables
load_dotenv()

# ── API Keys ──────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("ERROR: Missing required environment variable: ANTHROPIC_API_KEY")

# ── Server Identity ───────────────────────────
SERVER_NAME: str = os.getenv("SERVER_NAME", "my-mcp-server")
VERSION_NUMBER: str = os.getenv("VERSION_NUMBER", "1.0.0")
INSTRUCTIONS: str = os.getenv("INSTRUCTIONS", "MCP Server for AI Agent")

# ── File & Result Limits ──────────────────────
MAX_FILE_SIZE: int = 1 * 1024 * 1024    # 1 MB in bytes
MAX_RESULTS: int = 50
MAX_PATH_LENGTH: int = 260

# ── Timeout Settings ──────────────────────────
TOOL_TIMEOUT: int = 20      # seconds
SESSION_TIMEOUT: int = 300  # seconds

# ── Validation ────────────────────────────────
if TOOL_TIMEOUT <= 0:
    raise ValueError("TOOL_TIMEOUT must be positive")

if SESSION_TIMEOUT <= 0:
    raise ValueError("SESSION_TIMEOUT must be positive")

if MAX_FILE_SIZE <= 0:
    raise ValueError("MAX_FILE_SIZE must be positive")

# ── Path Configuration ────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

ALLOWED_DIRECTORIES: list[Path] = [
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "resources",
]

# Auto-create allowed directories if missing
for directory in ALLOWED_DIRECTORIES:
    directory.mkdir(parents=True, exist_ok=True)

# ── Log File Path ─────────────────────────────
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE: str = str(LOGS_DIR / "mcp_server.log")

# ── Config Summary ────────────────────────────
def get_config_summary() -> dict:
    return {
        "server_name": SERVER_NAME,
        "version": VERSION_NUMBER,
        "tool_timeout": TOOL_TIMEOUT,
        "session_timeout": SESSION_TIMEOUT,
        "max_file_size": MAX_FILE_SIZE,
        "max_results": MAX_RESULTS,
        "allowed_directories": [str(d) for d in ALLOWED_DIRECTORIES],
        "log_file": LOG_FILE,
    }