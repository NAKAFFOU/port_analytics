class PortAnalyticsError(Exception):
    """Base application exception."""


class ConfigurationError(PortAnalyticsError):
    """Raised when configuration is missing or invalid."""


class SourceConnectionError(PortAnalyticsError):
    """Raised when a source connection cannot be established."""


class DataValidationError(PortAnalyticsError):
    """Raised when extracted data fail the canonical contract."""


class MissingExchangeRateError(PortAnalyticsError):
    """Raised when no suitable exchange rate can be found."""
