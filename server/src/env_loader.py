#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def find_env_file(component):
    component_dir = Path(__file__).resolve().parent.parent
    candidates = [
        component_dir / ".env",
        Path(__file__).with_name(".env"),
        Path.cwd() / component / ".env",
        Path.cwd() / component / "src" / ".env",
    ]
    for env_file in candidates:
        if env_file.exists():
            return env_file
    return component_dir / ".env"


def load_env_file(env_file):
    if env_file.exists():
        load_dotenv(env_file, verbose=True)


def get_path_env(key, default, component):
    env_file = find_env_file(component)
    load_env_file(env_file)
    value = os.environ.get(key)
    if not value:
        return Path(default)
    path = Path(value).expanduser()
    return path if path.is_absolute() else env_file.parent / path


def load_required_env(env_file, required_keys, logger):
    load_env_file(env_file)

    values = {}
    for key in required_keys:
        value = os.environ.get(key)
        if not value:
            logger.error("Required environment variable is missing: %s", key)
            sys.exit(1)
        values[key] = value

    logger.info("Environment variables loaded successfully")
    return values


def parse_int_env(value, key, logger):
    try:
        return int(value)
    except ValueError:
        logger.error("%s must be an integer: %s", key, value)
        sys.exit(1)


def parse_bool_env(value, key, logger):
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    logger.error("%s must be a boolean: %s", key, value)
    sys.exit(1)
