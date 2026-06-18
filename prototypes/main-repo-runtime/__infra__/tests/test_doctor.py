from evozeus.doctor import FailureKind, classify_failure


def test_classify_tool_path_failure():
    assert classify_failure("zsh: command not found: gh") == FailureKind.TOOL_PATH


def test_classify_network_failure():
    assert classify_failure("fatal: unable to access repo: network timeout") == FailureKind.NETWORK


def test_classify_auth_failure():
    assert classify_failure("HTTP 403 Forbidden authentication failed") == FailureKind.AUTH
