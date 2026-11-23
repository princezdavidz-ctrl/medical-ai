from app.ai.contracts import AIModelRequest, AIModelResponse, AIProvider


class ModelUnavailable(RuntimeError):
    pass


class ModelGateway:
    """Provider-neutral gateway. It never changes provider class on fallback."""

    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}

    def register(self, provider: AIProvider) -> None:
        if provider.provider_class not in {"local", "hosted"}:
            raise ValueError("Provider class must be 'local' or 'hosted'")
        self._providers[provider.provider_class] = provider

    def generate(self, *, provider_class: str, request: AIModelRequest) -> AIModelResponse:
        provider = self._providers.get(provider_class)
        if provider is None:
            raise ModelUnavailable(f"No approved {provider_class} model provider is configured")
        return provider.generate(request)
