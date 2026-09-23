"""
ZedThema - Automated Codebook API Test

This test creates a temporary ZedThema research project and verifies:

1. Project creation
2. Parent code creation
3. Child code creation
4. Multi-level hierarchy
5. Code metadata
6. Code tree retrieval
7. Code editing
8. Circular hierarchy protection
9. Code deletion
10. Persistence through the API

The test uses only Python's standard library.
No additional packages are required.

IMPORTANT:
The test creates a project named:

    [AUTOMATED TEST] ZedThema Codebook

The project is intentionally left in the database because the
current API does not expose a DELETE PROJECT endpoint.
"""

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime


BASE_URL = "http://127.0.0.1:8000"

TEST_PROJECT_TITLE = (
    "[AUTOMATED TEST] ZedThema Codebook "
    + datetime.now().strftime("%Y%m%d-%H%M%S")
)


# ============================================================
# HTTP helper
# ============================================================

def request(method, path, data=None):
    """
    Send an HTTP request to the ZedThema API.

    Returns:
        status_code, response_data
    """

    url = BASE_URL + path

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:

            raw = response.read().decode("utf-8")

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw

            return response.status, parsed

    except urllib.error.HTTPError as exc:

        raw = exc.read().decode("utf-8")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw

        return exc.code, parsed

    except Exception as exc:

        print(f"\nERROR connecting to ZedThema:")
        print(exc)
        sys.exit(1)


# ============================================================
# Test reporting
# ============================================================

passed = 0
failed = 0
warnings = 0


def test_pass(message):
    global passed

    passed += 1
    print(f"[PASS] {message}")


def test_fail(message, details=None):
    global failed

    failed += 1

    print(f"[FAIL] {message}")

    if details is not None:
        print(f"       {details}")


def test_warning(message, details=None):
    global warnings

    warnings += 1

    print(f"[WARN] {message}")

    if details is not None:
        print(f"       {details}")


# ============================================================
# Extract ID helper
# ============================================================

def get_id(data):
    """
    ZedThema may return identifiers under different keys.
    Try the common possibilities.
    """

    if not isinstance(data, dict):
        return None

    for key in ("id", "pid", "cid", "project_id", "code_id"):

        if key in data:
            return data[key]

    return None


# ============================================================
# Main test
# ============================================================

print()
print("=" * 70)
print("ZedThema Automated Codebook API Test")
print("=" * 70)
print()
print(f"API: {BASE_URL}")
print(f"Test project: {TEST_PROJECT_TITLE}")
print()


# ------------------------------------------------------------
# 1. Health check
# ------------------------------------------------------------

status, data = request("GET", "/api/health")

if status == 200:
    test_pass("API health check")
else:
    test_fail(
        "API health check",
        f"HTTP {status}: {data}"
    )
    sys.exit(1)


# ------------------------------------------------------------
# 2. Create test project
# ------------------------------------------------------------

project_payload = {
    "title": TEST_PROJECT_TITLE,
    "description": "Automated codebook validation project.",
    "research_question": (
        "What factors influence adoption of digital transportation "
        "platforms?"
    ),
    "framework": "UTAUT2",
    "method": "Thematic analysis",
    "languages": ["English"],
}

status, project = request(
    "POST",
    "/api/projects",
    project_payload,
)

project_id = get_id(project)

if status == 200 and project_id:
    test_pass(
        f"Create test project ({project_id})"
    )
else:
    test_fail(
        "Create test project",
        f"HTTP {status}: {project}"
    )
    sys.exit(1)


# ============================================================
# Codebook hierarchy
#
# UTAUT2
# └── Performance Expectancy
#     ├── Convenience
#     │   └── Ease of Booking
#     ├── Time Saving
#     └── Reliability
# ============================================================


# ------------------------------------------------------------
# 3. Create parent code
# ------------------------------------------------------------

parent_payload = {
    "name": "Performance Expectancy",
    "definition": (
        "The extent to which a participant believes that "
        "using Yango provides useful transportation benefits."
    ),
    "inclusion": (
        "Statements about usefulness, convenience, time savings, "
        "reliability, productivity, or transportation benefits."
    ),
    "exclusion": (
        "Statements primarily about price, social pressure, "
        "or technical difficulties."
    ),
    "example": (
        "Yango helps me get transportation more quickly."
    ),
    "parent_id": None,
    "theory": "UTAUT2 – Performance Expectancy",
}

status, parent = request(
    "POST",
    f"/api/projects/{project_id}/codes",
    parent_payload,
)

parent_id = get_id(parent)

if status == 200 and parent_id:
    test_pass("Create parent code")
else:
    test_fail(
        "Create parent code",
        f"HTTP {status}: {parent}"
    )
    sys.exit(1)


# ------------------------------------------------------------
# 4. Create first child
# ------------------------------------------------------------

convenience_payload = {
    "name": "Convenience",
    "definition": (
        "Perceptions that Yango makes obtaining transportation "
        "easier or more convenient."
    ),
    "inclusion": (
        "Easier ride booking, easier access to drivers, "
        "or reduced effort in arranging transportation."
    ),
    "exclusion": (
        "Statements primarily concerning price or technical problems."
    ),
    "example": (
        "I can request a ride without having to look for a taxi."
    ),
    "parent_id": parent_id,
    "theory": "UTAUT2 – Performance Expectancy",
}

status, convenience = request(
    "POST",
    f"/api/projects/{project_id}/codes",
    convenience_payload,
)

convenience_id = get_id(convenience)

if status == 200 and convenience_id:
    test_pass("Create child code")
else:
    test_fail(
        "Create child code",
        f"HTTP {status}: {convenience}"
    )
    sys.exit(1)


# ------------------------------------------------------------
# 5. Create second child
# ------------------------------------------------------------

time_payload = {
    "name": "Time Saving",
    "definition": (
        "Perceptions that Yango reduces the time required "
        "to obtain transportation."
    ),
    "inclusion": (
        "Faster booking, reduced waiting time, "
        "or quicker access to drivers."
    ),
    "exclusion": (
        "General convenience statements without a time component."
    ),
    "example": (
        "I don't have to spend a long time looking for a taxi."
    ),
    "parent_id": parent_id,
    "theory": "UTAUT2 – Performance Expectancy",
}

status, time_code = request(
    "POST",
    f"/api/projects/{project_id}/codes",
    time_payload,
)

time_id = get_id(time_code)

if status == 200 and time_id:
    test_pass("Create second child code")
else:
    test_fail(
        "Create second child code",
        f"HTTP {status}: {time_code}"
    )


# ------------------------------------------------------------
# 6. Create third child
# ------------------------------------------------------------

reliability_payload = {
    "name": "Reliability",
    "definition": (
        "Perceptions that Yango provides dependable "
        "and predictable transportation."
    ),
    "inclusion": (
        "Driver availability, dependable service, "
        "predictable pickup, or consistency."
    ),
    "exclusion": (
        "Statements about unrelated technical problems."
    ),
    "example": (
        "I normally know that I will find a driver when I request one."
    ),
    "parent_id": parent_id,
    "theory": "UTAUT2 – Performance Expectancy",
}

status, reliability = request(
    "POST",
    f"/api/projects/{project_id}/codes",
    reliability_payload,
)

reliability_id = get_id(reliability)

if status == 200 and reliability_id:
    test_pass("Create third child code")
else:
    test_fail(
        "Create third child code",
        f"HTTP {status}: {reliability}"
    )


# ------------------------------------------------------------
# 7. Create third hierarchy level
# ------------------------------------------------------------

booking_payload = {
    "name": "Ease of Booking",
    "definition": (
        "Perceptions that requesting a Yango ride is simple "
        "and requires little effort."
    ),
    "inclusion": (
        "Simple booking process, few steps, easy ride requests."
    ),
    "exclusion": (
        "General convenience that is unrelated to booking."
    ),
    "example": (
        "It only takes me a few steps to request a ride."
    ),
    "parent_id": convenience_id,
    "theory": "UTAUT2 – Effort Expectancy",
}

status, booking = request(
    "POST",
    f"/api/projects/{project_id}/codes",
    booking_payload,
)

booking_id = get_id(booking)

if status == 200 and booking_id:
    test_pass("Create third-level child code")
else:
    test_fail(
        "Create third-level child code",
        f"HTTP {status}: {booking}"
    )


# ------------------------------------------------------------
# 8. Retrieve code tree
# ------------------------------------------------------------

status, tree = request(
    "GET",
    f"/api/projects/{project_id}/code-tree",
)

if status == 200:

    tree_text = json.dumps(tree)

    required_codes = [
        "Performance Expectancy",
        "Convenience",
        "Time Saving",
        "Reliability",
        "Ease of Booking",
    ]

    missing = [
        name
        for name in required_codes
        if name not in tree_text
    ]

    if not missing:
        test_pass("Retrieve complete hierarchical code tree")
    else:
        test_fail(
            "Retrieve complete hierarchical code tree",
            f"Missing: {missing}"
        )

else:

    test_fail(
        "Retrieve code tree",
        f"HTTP {status}: {tree}"
    )


# ------------------------------------------------------------
# 9. Verify metadata
# ------------------------------------------------------------

metadata_text = json.dumps(parent)

required_metadata = [
    "definition",
    "inclusion",
    "exclusion",
    "example",
    "theory",
]

missing_metadata = [
    key
    for key in required_metadata
    if key not in metadata_text
]

if not missing_metadata:
    test_pass("Code metadata returned by API")
else:
    test_fail(
        "Code metadata returned by API",
        f"Missing fields: {missing_metadata}"
    )


# ------------------------------------------------------------
# 10. Update code
# ------------------------------------------------------------

update_payload = {
    "definition": (
        "UPDATED: The extent to which a participant believes "
        "that Yango improves transportation outcomes."
    )
}

status, updated = request(
    "PATCH",
    f"/api/projects/{project_id}/codes/{convenience_id}",
    update_payload,
)

if status == 200:

    updated_text = json.dumps(updated)

    if "UPDATED" in updated_text:
        test_pass("Update existing code")
    else:
        test_warning(
            "Update endpoint returned successfully",
            "Response did not visibly contain updated text."
        )

else:

    test_fail(
        "Update existing code",
        f"HTTP {status}: {updated}"
    )


# ------------------------------------------------------------
# 11. Test circular hierarchy protection
#
# Try to make the parent a child of its own descendant.
#
# Expected behaviour:
#
#     HTTP 400 / 409 / 422
#
# or another explicit rejection.
# ------------------------------------------------------------

circular_payload = {
    "parent_id": booking_id
}

status, circular_result = request(
    "PATCH",
    f"/api/projects/{project_id}/codes/{parent_id}",
    circular_payload,
)

if status >= 400 and status < 500:

    test_pass(
        "Circular hierarchy protection"
    )

else:

    test_fail(
        "Circular hierarchy protection",
        (
            f"API accepted an invalid circular relationship "
            f"(HTTP {status}). This should be investigated."
        )
    )

    # Attempt to restore the parent code so the test does not
    # intentionally leave a circular hierarchy behind.

    restore_payload = {
        "parent_id": None
    }

    request(
        "PATCH",
        f"/api/projects/{project_id}/codes/{parent_id}",
        restore_payload,
    )


# ------------------------------------------------------------
# 12. Test duplicate code behaviour
# ------------------------------------------------------------

duplicate_payload = {
    "name": "Convenience",
    "definition": "Duplicate-code test.",
    "parent_id": parent_id,
    "theory": "UTAUT2",
}

status, duplicate_result = request(
    "POST",
    f"/api/projects/{project_id}/codes",
    duplicate_payload,
)

if status >= 400:

    test_pass(
        "Duplicate code rejected by API"
    )

else:

    test_warning(
        "Duplicate code was accepted",
        (
            "The API currently permits duplicate code names. "
            "This may be acceptable, but the UI should clearly "
            "handle or warn about duplicates."
        )
    )

    duplicate_id = get_id(duplicate_result)

    if duplicate_id:

        request(
            "DELETE",
            f"/api/projects/{project_id}/codes/{duplicate_id}",
        )


# ------------------------------------------------------------
# 13. Delete temporary third-level code
# ------------------------------------------------------------

status, deleted = request(
    "DELETE",
    f"/api/projects/{project_id}/codes/{booking_id}",
)

if status == 200:

    test_pass("Delete code")

else:

    test_fail(
        "Delete code",
        f"HTTP {status}: {deleted}"
    )


# ------------------------------------------------------------
# 14. Verify deleted code is gone
# ------------------------------------------------------------

status, final_tree = request(
    "GET",
    f"/api/projects/{project_id}/code-tree",
)

if status == 200:

    final_text = json.dumps(final_tree)

    if "Ease of Booking" not in final_text:
        test_pass("Deleted code removed from code tree")
    else:
        test_fail(
            "Deleted code removed from code tree",
            "Deleted code still appears in the hierarchy."
        )

else:

    test_fail(
        "Verify final code tree",
        f"HTTP {status}: {final_tree}"
    )


# ============================================================
# Final report
# ============================================================

print()
print("=" * 70)
print("TEST RESULTS")
print("=" * 70)
print()
print(f"Passed   : {passed}")
print(f"Failed   : {failed}")
print(f"Warnings : {warnings}")
print()
print(f"Test project ID: {project_id}")
print(f"Test project:   {TEST_PROJECT_TITLE}")
print()

if failed == 0:

    print("RESULT: CODEBOOK TEST PASSED")
    print()
    print(
        "The core ZedThema codebook API is functioning."
    )

else:

    print("RESULT: CODEBOOK TEST FOUND PROBLEMS")
    print()
    print(
        "Review the failed tests before proceeding."
    )

print()
print("=" * 70)

sys.exit(1 if failed else 0)
