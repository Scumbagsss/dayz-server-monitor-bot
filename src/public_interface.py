"""Portfolio-only interface skeleton. This module is intentionally non-runnable."""


class DayzServerMonitorBotInterface:
    """Architectural surface of the private production implementation."""

    async def query_server(self, *args, **kwargs):
        """Public portfolio signature only. Production logic is private."""
        raise NotImplementedError("Production implementation is private")

    async def store_snapshot(self, *args, **kwargs):
        """Public portfolio signature only. Production logic is private."""
        raise NotImplementedError("Production implementation is private")

    async def render_status(self, *args, **kwargs):
        """Public portfolio signature only. Production logic is private."""
        raise NotImplementedError("Production implementation is private")

    async def build_activity_report(self, *args, **kwargs):
        """Public portfolio signature only. Production logic is private."""
        raise NotImplementedError("Production implementation is private")

