"""
utils.py — Shared utilities untuk Portfolio Automation Pipeline.

Fungsi:
  - Logger setup dengan rotasi file
  - Date formatting helpers
  - Error handling decorator
  - Config loader
"""

import os
import sys
import yaml
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from dotenv import load_dotenv

# ─── Path ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"
LOGS_DIR = PROJECT_ROOT / "logs"

# ─── Config Loader ───────────────────────────────────────────────────────────

def load_config():
    """Load config.yaml sebagai dictionary."""
    if not CONFIG_PATH.exists():
        print(f"[ERROR] Config tidak ditemukan: {CONFIG_PATH}", file=sys.stderr)
        print("Copy config.yaml.example ke config.yaml lalu edit.", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def load_env():
    """Load .env file. Optional — fallback ke environment variable."""
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    else:
        print(f"[WARN] .env tidak ditemukan di {ENV_PATH}")
        print("Gunakan environment variable langsung atau copy .env.example")


# ─── Logger ──────────────────────────────────────────────────────────────────

def setup_logger(name="portfolio-automation", level=None):
    """
    Setup logger dengan console + file handler (rotating).

    Args:
        name: Nama logger
        level: Log level (default dari config atau INFO)

    Returns:
        logging.Logger instance
    """
    if level is None:
        try:
            config = load_config()
            level = getattr(logging, config.get("logging", {}).get("level", "INFO"))
        except Exception:
            level = logging.INFO

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Hindari duplicate handler kalau dipanggil ulang
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler (dengan rotasi)
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        config = load_config()
        log_cfg = config.get("logging", {})
        log_filename = log_cfg.get("file", "sync.log")
        # Handle path relatif (tanpa "logs/" prefix) dan absolut
        log_file = Path(log_filename)
        if not log_file.is_absolute():
            log_file = LOGS_DIR / log_file.name  # ambil hanya nama file
        max_bytes = log_cfg.get("max_bytes", 10 * 1024 * 1024)
        backup_count = log_cfg.get("backup_count", 3)

        fh = RotatingFileHandler(
            str(log_file), maxBytes=max_bytes, backupCount=backup_count
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"Gagal setup file logger: {e}")

    return logger


# ─── Date Helpers ────────────────────────────────────────────────────────────

def format_datetime(dt, fmt="%Y-%m-%d %H:%M:%S"):
    """
    Format datetime object ke string. Handle None dan berbagai format.
    """
    if dt is None:
        return ""
    if isinstance(dt, str):
        # Coba parse berbagai format umum
        for f in [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(dt, f)
                break
            except ValueError:
                continue
        else:
            return dt  # Return as-is kalau gak bisa parse
    if isinstance(dt, datetime):
        return dt.strftime(fmt)
    return str(dt)


def now_str(fmt="%Y-%m-%d %H:%M:%S"):
    """Return current time sebagai string."""
    return datetime.now(timezone.utc).strftime(fmt)


def days_since_last_commit(last_commit_str):
    """Hitung hari sejak commit terakhir."""
    if not last_commit_str:
        return None
    try:
        last = datetime.strptime(last_commit_str[:10], "%Y-%m-%d")
        delta = datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc)
        return delta.days
    except Exception:
        return None


# ─── Error Handler Decorator ─────────────────────────────────────────────────

def handle_errors(logger=None):
    """
    Decorator untuk error handling yang konsisten.
    Log error + return status dict instead of throwing.

    Usage:
        @handle_errors(logger=my_logger)
        def my_func():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = setup_logger(func.__name__)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error di {func.__name__}: {e}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error": str(e),
                    "function": func.__name__,
                }
        return wrapper
    return decorator


# ─── Validation ──────────────────────────────────────────────────────────────

def validate_env(required_vars):
    """
    Validasi environment variable yang diperlukan.

    Args:
        required_vars: List of env var names

    Returns:
        (is_valid, missing_vars)
    """
    missing = [v for v in required_vars if not os.getenv(v)]
    return len(missing) == 0, missing


# ─── Quick Test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test
    load_env()
    logger = setup_logger()
    logger.info("Utils module loaded successfully")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info(f"Config exists: {CONFIG_PATH.exists()}")
    print(f"Now: {now_str()}")
    print(f"Days since 2025-01-01: {days_since_last_commit('2025-01-01')}")
