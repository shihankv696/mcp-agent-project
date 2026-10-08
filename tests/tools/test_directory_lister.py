"""
Tests for tools/directory_lister.py

HOW TO RUN THIS FILE:
    Make sure your virtual environment is active:

    Then from your project root folder run:
    python tests/test_directory_lister.py

HOW THESE TESTS WORK:
    Your list_directory function returns a list containing
    one TextContent object. The TextContent object has a
    'text' field which contains a JSON string.

    These tests:
    1. Call list_directory directly (no MCP or Claude needed)
    2. Extract the text from TextContent
    3. Parse the JSON string back into a dictionary
    4. Check the dictionary has the right values
"""

import asyncio
import json
import os
import sys

# Fix — go up THREE levels to reach project root
# __file__ = tests/tools/test_directory_lister.py
# parent 1 = tests/tools/
# parent 2 = tests/
# parent 3 = mcp-agent-project/  ← project root
project_root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)
sys.path.insert(0, project_root)

from pathlib import Path
from server.logger import get_logger 

# ─────────────────────────────────────────────────────────────
# PATH SETUP
# This block makes sure Python can find your project files
# no matter where you run the test from.
# It adds your project root folder to Python's search path.
# ─────────────────────────────────────────────────────────────
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.directory_lister import list_directory



# ─────────────────────────────────────────────────────────────
# SAMPLE DATA SETUP
# Creates temporary test folders and files that tests use.
# These are created fresh each time tests run.
# ─────────────────────────────────────────────────────────────

# Path to the sample data folder (sits inside tests/)
SAMPLE_DIR = project_root / "tests" / "sample_data"
logger = get_logger(__name__) 

def create_sample_data():
    """
    Creates sample files and folders for testing.
    Called automatically before tests run.
    """
    print("\n📁 Setting up sample test data...")

    # Create the main sample_data folder
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    # Create sample text files with content
    (SAMPLE_DIR / "notes.txt").write_text("These are my notes for the project.")
    (SAMPLE_DIR / "plan.md").write_text("# Project Plan\n- Step 1\n- Step 2")

    # Create an empty subfolder
    (SAMPLE_DIR / "archive").mkdir(exist_ok=True)

    print("   Created: notes.txt")
    print("   Created: plan.md")
    print("   Created: archive/ (folder)")
    print("   Sample data ready.\n")


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTION
# Your function returns TextContent with JSON inside .text
# This helper extracts and parses that JSON for you
# so you don't repeat this in every test.
# ─────────────────────────────────────────────────────────────

def extract_result(response):
    """
    Takes the raw return value from list_directory
    and extracts the parsed JSON dictionary from it.

    Your function returns:
        [TextContent(type="text", text='{"success": true, ...}')]

    This helper returns:
        {"success": True, "entries": [...], ...}
    """
    # response is a list — get the first item
    text_content = response[0]

    # text_content.text is a JSON string — parse it
    return json.loads(text_content.text)


# ─────────────────────────────────────────────────────────────
# TEST FUNCTIONS
# Each test checks one specific behaviour of list_directory.
# Each test prints PASS or FAIL with a reason.
# ─────────────────────────────────────────────────────────────

async def test_1_valid_directory():
    """
    TEST 1 — List a valid directory
    Checks that listing sample_data returns correct structure
    and contains the files we created.
    """
    print("─" * 55)
    print("TEST 1 — List a valid directory")
    print("─" * 55)

    response = await list_directory(str(SAMPLE_DIR))
    result = extract_result(response)

    print(f"   Raw result preview:")
    print(f"   success      → {result.get('success')}")
    print(f"   total_shown  → {result.get('total_shown')}")
    print(f"   truncated    → {result.get('truncated')}")
    print(f"   entries      → {[e['name'] for e in result.get('entries', [])]}")

    # Check 1 — success must be True
    assert result.get("success") == True, \
        f"FAIL: Expected success=True but got {result.get('success')}"

    # Check 2 — entries must be a list
    assert isinstance(result.get("entries"), list), \
        "FAIL: Expected entries to be a list"

    # Check 3 — must find at least 2 items (notes.txt, plan.md)
    assert result.get("total_shown") >= 2, \
        f"FAIL: Expected at least 2 items but got {result.get('total_shown')}"

    # Check 4 — every entry must have all required keys
    required_keys = {"name", "type", "size_bytes", "modified"}
    for entry in result["entries"]:
        missing = required_keys - entry.keys()
        assert not missing, \
            f"FAIL: Entry is missing keys: {missing}"

    print("   ✅ TEST 1 PASSED\n")


async def test_2_correct_types():
    """
    TEST 2 — Check file vs directory types are correct
    notes.txt and plan.md should be type 'file'
    archive should be type 'directory'
    Files should have a size_bytes value (not None)
    Folders should have size_bytes as None
    """
    print("─" * 55)
    print("TEST 2 — Check file and directory types")
    print("─" * 55)

    response = await list_directory(str(SAMPLE_DIR))
    result = extract_result(response)

    # Build a lookup dictionary: name → entry
    # Makes it easy to find a specific file by name
    entries_by_name = {e["name"]: e for e in result["entries"]}

    print(f"   Found entries: {list(entries_by_name.keys())}")

    # Check notes.txt is type "file"
    assert "notes.txt" in entries_by_name, \
        "FAIL: notes.txt not found in results"
    assert entries_by_name["notes.txt"]["type"] == "file", \
        f"FAIL: notes.txt should be type 'file' but got '{entries_by_name['notes.txt']['type']}'"

    # Check plan.md is type "file"
    assert "plan.md" in entries_by_name, \
        "FAIL: plan.md not found in results"
    assert entries_by_name["plan.md"]["type"] == "file", \
        f"FAIL: plan.md should be type 'file' but got '{entries_by_name['plan.md']['type']}'"

    # Check archive is type "directory"
    assert "archive" in entries_by_name, \
        "FAIL: archive folder not found in results"
    assert entries_by_name["archive"]["type"] == "directory", \
        f"FAIL: archive should be type 'directory' but got '{entries_by_name['archive']['type']}'"

    # Check files have a real size (not None)
    assert entries_by_name["notes.txt"]["size_bytes"] is not None, \
        "FAIL: notes.txt should have a size_bytes value, not None"
    assert entries_by_name["notes.txt"]["size_bytes"] > 0, \
        "FAIL: notes.txt size_bytes should be greater than 0"

    # Check directory has None for size
    assert entries_by_name["archive"]["size_bytes"] is None, \
        f"FAIL: archive folder size_bytes should be None but got {entries_by_name['archive']['size_bytes']}"

    print(f"   notes.txt type  → {entries_by_name['notes.txt']['type']} ✓")
    print(f"   notes.txt size  → {entries_by_name['notes.txt']['size_bytes']} bytes ✓")
    print(f"   plan.md type    → {entries_by_name['plan.md']['type']} ✓")
    print(f"   archive type    → {entries_by_name['archive']['type']} ✓")
    print(f"   archive size    → {entries_by_name['archive']['size_bytes']} ✓")
    print("   ✅ TEST 2 PASSED\n")


async def test_3_empty_path():
    """
    TEST 3 — Empty directory_path input
    When called with an empty string, the function
    should return an error message, not crash.
    """
    print("─" * 55)
    print("TEST 3 — Empty directory_path")
    print("─" * 55)

    response = await list_directory("")
    text_content = response[0]
    raw_text = text_content.text

    print(f"   Raw response text: {raw_text}")

    # Check it contains the word "Error"
    assert "Error" in raw_text, \
        f"FAIL: Expected an error message but got: {raw_text}"

    # Check it does NOT crash and return success
    # The response should NOT be valid JSON with success=True
    try:
        parsed = json.loads(raw_text)
        assert parsed.get("success") != True, \
            "FAIL: Empty path should not return success=True"
    except json.JSONDecodeError:
        # Not JSON at all — that is fine, it is an error message string
        pass

    print(f"   Correctly returned error for empty path ✓")
    print("   ✅ TEST 3 PASSED\n")


async def test_4_nonexistent_path():
    """
    TEST 4 — Path that does not exist
    Should return a clear error message, not crash.
    """
    print("─" * 55)
    print("TEST 4 — Path that does not exist")
    print("─" * 55)

    fake_path = str(project_root / "tests" / "this_folder_does_not_exist_xyz")
    response = await list_directory(fake_path)
    text_content = response[0]
    raw_text = text_content.text

    print(f"   Raw response text: {raw_text}")

    # Should contain "Error"
    assert "Error" in raw_text, \
        f"FAIL: Expected an error message but got: {raw_text}"

    # Should NOT return success
    try:
        parsed = json.loads(raw_text)
        assert parsed.get("success") != True, \
            "FAIL: Non-existent path should not return success=True"
    except json.JSONDecodeError:
        pass

    print(f"   Correctly returned error for non-existent path ✓")
    print("   ✅ TEST 4 PASSED\n")


async def test_5_file_instead_of_directory():
    """
    TEST 5 — Path points to a FILE, not a folder
    Should return a clear error saying it is a file.
    Should NOT try to list the file as a directory.
    """
    print("─" * 55)
    print("TEST 5 — Path is a file not a directory")
    print("─" * 55)

    # Pass the path to notes.txt (a file, not a folder)
    file_path = str(SAMPLE_DIR / "notes.txt")
    response = await list_directory(file_path)
    text_content = response[0]
    raw_text = text_content.text

    print(f"   Raw response text: {raw_text}")

    # Should contain "Error"
    assert "Error" in raw_text, \
        f"FAIL: Expected an error message but got: {raw_text}"

    # Should mention "file" in the error message
    assert "file" in raw_text.lower(), \
        f"FAIL: Error message should mention 'file' but got: {raw_text}"

    # Should NOT return success
    try:
        parsed = json.loads(raw_text)
        assert parsed.get("success") != True, \
            "FAIL: File path should not return success=True"
    except json.JSONDecodeError:
        pass

    print(f"   Correctly returned error for file path ✓")
    print("   ✅ TEST 5 PASSED\n")


async def test_6_modified_time_format():
    """
    TEST 6 — Modified time is readable ISO format
    The modified field should look like:
    "2026-06-22T10:30:00" not a raw number like 1718888888.0
    """
    print("─" * 55)
    print("TEST 6 — Modified time is readable ISO format")
    print("─" * 55)

    response = await list_directory(str(SAMPLE_DIR))
    result = extract_result(response)

    for entry in result["entries"]:
        modified = entry.get("modified")

        if modified is not None:
            print(f"   {entry['name']} modified → {modified}")

            # ISO format contains a "T" separating date and time
            assert "T" in modified, \
                f"FAIL: modified time for {entry['name']} is not ISO format: {modified}"

            # Should start with a 4-digit year like "2025" or "2026"
            assert modified[:4].isdigit(), \
                f"FAIL: modified time should start with year digits: {modified}"

    print("   ✅ TEST 6 PASSED\n")


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# Runs all tests in order and shows a final summary.
# ─────────────────────────────────────────────────────────────

async def run_all_tests():
    print("\n" + "═" * 55)
    print("   RUNNING TESTS FOR list_directory")
    print("═" * 55)

    # Create sample data before any tests run
    create_sample_data()

    # Track results
    passed = 0
    failed = 0
    failed_tests = []

    # List of all test functions
    tests = [
        test_1_valid_directory,
        test_2_correct_types,
        test_3_empty_path,
        test_4_nonexistent_path,
        test_5_file_instead_of_directory,
        test_6_modified_time_format,
    ]

    # Run each test and catch failures
    for test_fn in tests:
        try:
            await test_fn()
            passed += 1
        except AssertionError as e:
            # Test failed with our own assert message
            print(f"   ❌ {test_fn.__name__} FAILED")
            print(f"      Reason: {e}\n")
            failed += 1
            failed_tests.append(test_fn.__name__)
        except Exception as e:
            # Test crashed unexpectedly
            print(f"   💥 {test_fn.__name__} CRASHED UNEXPECTEDLY")
            print(f"      Error type: {type(e).__name__}")
            print(f"      Details:    {e}\n")
            failed += 1
            failed_tests.append(test_fn.__name__)

    # Final summary
    print("═" * 55)
    print(f"   RESULTS: {passed} passed   {failed} failed")
    print("═" * 55)

    if failed == 0:
        print("\n   🎉 ALL TESTS PASSED")
        print("   Your list_directory tool is working correctly.")
        print("   You are ready to test in MCP Inspector.\n")
    else:
        print(f"\n   ⚠️  {failed} TEST(S) FAILED:")
        for name in failed_tests:
            print(f"      - {name}")
        print("\n   Fix the failing tests before moving to MCP Inspector.\n")


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# This runs when you do: python tests/test_directory_lister.py
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_all_tests())