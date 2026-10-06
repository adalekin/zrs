from internal.config.installation import ConfigurationError, Settings, load_settings

__all__ = ["ConfigurationError", "Settings", "load_settings", "settings"]

_settings: Settings | None = None


def __getattr__(name: str) -> Settings:
    # ``settings`` is read on first access, not at import, so that a start-up script can
    # import ``ConfigurationError`` before the settings are validated.
    global _settings
    if name == "settings":
        if _settings is None:
            _settings = load_settings()
        return _settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
