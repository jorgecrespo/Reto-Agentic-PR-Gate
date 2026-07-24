import pytest

from pr_gate.infrastructure.patches import (
    PatchValidationError,
    normalize_hunk_counts,
    validate_patch,
    validate_patch_shape,
)

PATH = "examples/demo_ecommerce/app/orders.py"
PATCH = f"""diff --git a/{PATH} b/{PATH}
--- a/{PATH}
+++ b/{PATH}
@@ -1 +1 @@
-old
+new
"""


def test_accepts_allowed_unified_diff() -> None:
    assert validate_patch_shape(PATCH, ("examples/demo_ecommerce/",)) == (PATH,)


def test_rejects_path_traversal() -> None:
    with pytest.raises(PatchValidationError):
        validate_patch_shape(PATCH.replace(PATH, "../.env"), ("examples/",))


def test_rejects_runner_configuration_and_secrets() -> None:
    with pytest.raises(PatchValidationError, match="protegido"):
        validate_patch(PATCH.replace(PATH, "Dockerfile"), ("",))
    with pytest.raises(PatchValidationError, match="secreto"):
        validate_patch(PATCH + "+ api_key='abcdefghijklmnop'\n", ("examples/",))


def test_rejects_hunk_with_incorrect_line_counts() -> None:
    invalid = PATCH.replace("@@ -1 +1 @@", "@@ -1,7 +1,7 @@")

    with pytest.raises(PatchValidationError, match="conteos"):
        validate_patch(invalid, ("examples/demo_ecommerce/",))


def test_normalizes_hunk_counts_without_changing_content() -> None:
    invalid = PATCH.replace("@@ -1 +1 @@", "@@ -1,7 +1,7 @@")

    normalized = normalize_hunk_counts(invalid)

    assert "@@ -1,1 +1,1 @@" in normalized
    assert "-old\n+new" in normalized
    assert normalized.endswith("\n")
    assert validate_patch(normalized, ("examples/demo_ecommerce/",)).paths == (PATH,)


def test_normalization_preserves_empty_regression_patch() -> None:
    assert normalize_hunk_counts("\n") == ""


def test_normalization_adds_missing_context_prefix() -> None:
    malformed = PATCH.replace("-old\n+new", "old\n-old\n+new")

    normalized = normalize_hunk_counts(malformed)

    assert " old\n-old\n+new" in normalized
