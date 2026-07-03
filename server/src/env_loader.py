#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sys

from dotenv import load_dotenv


def load_required_env(env_file, required_keys, logger):
    if not env_file.exists():
        logger.error(".env file not found: %s", env_file)
        sys.exit(1)

    load_dotenv(env_file, verbose=True)

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
