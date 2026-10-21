class RequestStateError(ValueError):
    """Solicitação duplicada ou já analisada."""


class ExceptionNotNeededError(ValueError):
    """O cancelamento já cumpre a antecedência mínima."""
