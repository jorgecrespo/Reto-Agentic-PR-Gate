import pytest

from pr_gate.infrastructure.patches import (
    PatchValidationError,
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
