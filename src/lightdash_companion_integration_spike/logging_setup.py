import logging

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
PACKAGE_LOGGER = "lightdash_companion_integration_spike"


def configure(*, level: str) -> None:
    """
    Send this package's logs to stderr at the given level (e.g. DEBUG, INFO).

    Only our logger is configured, so third-party libraries stay quiet.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    package_logger = logging.getLogger(PACKAGE_LOGGER)
    package_logger.handlers = [handler]
    package_logger.setLevel(level.upper())
    package_logger.propagate = False
