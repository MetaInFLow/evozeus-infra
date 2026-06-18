from textual.app import App

from evozeus.tui.app import EvoZeusApp


def test_tui_app_is_textual_app_with_evozeus_title():
    assert issubclass(EvoZeusApp, App)
    assert EvoZeusApp.TITLE == "EvoZeus"
