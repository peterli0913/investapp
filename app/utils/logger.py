"""简单日志封装。"""
from __future__ import annotations

import logging
import sys

_LOGGER_CACHE: dict[str, logging.Logger] = {}


def get_logger(name: str = "stock_assistant") -> logging.Logger:
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(h)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _LOGGER_CACHE[name] = logger
    return logger
