from pr_gate.infrastructure.runner import classify_command_result


def test_classifies_functional_failure_separately_from_infrastructure() -> None:
    assert classify_command_result(1, "", "AssertionError: expected total") == "ASSERTION_FAILURE"
    assert (
        classify_command_result(None, "", "Docker daemon unavailable", True)
        == "INFRASTRUCTURE_ERROR"
    )
    assert classify_command_result(1, "", "ModuleNotFoundError: x") == "IMPORT_ERROR"
