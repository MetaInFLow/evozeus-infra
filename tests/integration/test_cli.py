from typer.testing import CliRunner

from evozeus_runtime.cli.main import app


def test_status_command_prints_runtime_status():
    result = CliRunner().invoke(app, ["status"])

    assert result.exit_code == 0
    assert "scanner-runner-runtime" in result.stdout

