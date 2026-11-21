from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override


class NoopProductTelemetry(ProductTelemetryClient):
    """Disable Chroma product events for this local-only application."""

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        return None
