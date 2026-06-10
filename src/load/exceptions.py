"""Custom exceptions for PostgreSQL load layer."""


class PostgresError(Exception):
    """Base class for any error with PostgresLoader."""


class PostgresConnectionError(PostgresError):
    """Cannot connect to Postgres (db down, wrong creds, network)."""


class PostgresUpsertError(PostgresError):
    """Failed to upsert rates (constraint violation, transaction rollback)."""
