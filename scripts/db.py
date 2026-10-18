"""Shared MySQL connection settings, read from the environment."""
import os

import mysql.connector


def config():
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "database": os.getenv("DB_NAME", "shop"),
        "user": os.getenv("DB_USER", "app"),
        "password": os.getenv("DB_PASSWORD", "apppw"),
    }


def connect(**overrides):
    return mysql.connector.connect(**{**config(), **overrides})
