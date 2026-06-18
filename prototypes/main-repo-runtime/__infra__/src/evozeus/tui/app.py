from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, ListItem, ListView, Static


class EvoZeusApp(App[None]):
    TITLE = "EvoZeus"

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(
            ListItem(Static("Current Session")),
            ListItem(Static("Debug Verdicts")),
            ListItem(Static("Case Drafts")),
            ListItem(Static("Skill Proposals")),
            ListItem(Static("Factor Runtime")),
            ListItem(Static("Community Contributions")),
            ListItem(Static("History")),
            ListItem(Static("Settings / Privacy")),
        )
        yield Footer()
