import asyncio
import sys
from pathlib import Path
from tools.file_reader import file_read

async def run_tests():
    result = await file_read("tests/sample.txt")
    print(result)

    result = await file_read("tests/does_not_exist.txt")
    print(result)

    result = await file_read("")
    print(result)

    result = await file_read("../../../some/system/path")
    print(result)

if __name__ == "__main__":
    asyncio.run(run_tests())