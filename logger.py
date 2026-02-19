"""
utils/logger.py  –  Centralised logging configuration
"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "forexbot", level: int = logging.INFO) -> logging.Logger:
    Path("logs").mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(f"logs/{name}.log")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Also configure root logger so all modules get the same format
    logging.basicConfig(handlers=[ch, fh], level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    return logger
