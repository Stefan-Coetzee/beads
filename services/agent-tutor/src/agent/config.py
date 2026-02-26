"""
Thin compatibility shim — all values come from ltt_settings.

graph.py accesses config via config.model.tutor_model and
config.agent.use_react_agent etc.  This shim preserves that interface
so graph.py does not need to change, while routing everything through
the single get_settings() call.
"""

from ltt_settings import Settings, get_settings


class _ModelConfig:
    """Proxy for config.model.* — reads from central Settings."""

    def __init__(self, s: Settings) -> None:
        self._s = s

    @property
    def tutor_model(self) -> str:
        return self._s.tutor_model

    @property
    def tutor_temperature(self) -> float:
        return 0.7  # reasonable fixed default; promote to LTT_TUTOR_TEMPERATURE if needed

    @property
    def max_tokens(self) -> int:
        return self._s.max_tokens

    @property
    def thinking_enabled(self) -> bool:
        return self._s.thinking_enabled

    @property
    def thinking_budget_tokens(self) -> int:
        return self._s.thinking_budget_tokens


class _AgentConfig:
    """Proxy for config.agent.* — reads from central Settings."""

    def __init__(self, s: Settings) -> None:
        self._s = s

    @property
    def use_react_agent(self) -> bool:
        return True  # always use react agent; legacy custom graph removed

    @property
    def max_conversation_turns(self) -> int:
        return self._s.max_conversation_turns

    @property
    def ready_tasks_limit(self) -> int:
        return self._s.ready_tasks_limit


class Config:
    """
    Compatibility wrapper around Settings.

    Presents the nested config.model / config.agent interface that
    graph.py expects, backed by the central ltt_settings singleton.
    """

    def __init__(self) -> None:
        self._s = get_settings()
        self.model = _ModelConfig(self._s)
        self.agent = _AgentConfig(self._s)


def get_config() -> Config:
    """Return a Config backed by the central settings singleton."""
    return Config()


# Module-level default — graph.py imports this in a few places
default_config = Config()
