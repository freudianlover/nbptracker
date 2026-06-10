import pytest
from src.load.postgres import PostgresLoader
from src.load.exceptions import PostgresError, PostgresConnectionError, PostgresUpsertError
from unittest.mock import MagicMock
from datetime import date
import psycopg2


def test_empty_list(mocker, postgres_loader):
    mock_conn = MagicMock()
    mock_execute_values = mocker.patch('src.load.postgres.execute_values')

    # Act
    inserted, updated = postgres_loader.upsert_rates(mock_conn, [])

    # Assert
    assert inserted == 0
    assert updated == 0
    # ważne: NIE wywołane dla pustego inputu
    mock_execute_values.assert_not_called()


def test_upsert_inserts_new_rates(postgres_loader, sample_exchange_rates, mocker):
    """Happy path: all rates are new inserts, returns (count, 0)."""
    # Arrange
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    # Cursor jest context managerem — musisz to skonfigurować
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock execute_values — zwraca True dla każdego rate (wszystkie inserty)
    mock_execute_values = mocker.patch(
        'src.load.postgres.execute_values',
        return_value=[(True,)] * len(sample_exchange_rates),  # 3 inserty
    )

    # Act
    inserted, updated = postgres_loader.upsert_rates(
        mock_conn, sample_exchange_rates)

    # Assert
    assert inserted == 3
    assert updated == 0
    # TODO sprawdź też że execute_values zostało wywołane RAZ (assert_called_once)
    mock_execute_values.assert_called_once()


def test_upsert_mixed_insert_update_counts(postgres_loader, sample_exchange_rates, mocker):
    """3 rates: 2 inserts + 1 update should return (2, 1)."""
    # Arrange
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_execute_values = mocker.patch(
        'src.load.postgres.execute_values',
        return_value=[(True,), (False,), (True,)],
    )

    inserted, updated = postgres_loader.upsert_rates(
        mock_conn, sample_exchange_rates
    )

    assert inserted == 2
    assert updated == 1
    mock_execute_values.assert_called_once()

    # TODO:
    # 1. Zrób mock_conn i mock_cursor jak wyżej (with context manager)
    # 2. Mock execute_values żeby zwrócił mixed:
    #    [(True,), (False,), (True,)]  -- True=inserted, False=updated (xmax=0 logic)
    # 3. Act: wywołaj upsert_rates
    # 4. Assert: inserted == 2, updated == 1


def test_connection_raises_postgres_error_on_db_down(postgres_loader, mocker):
    """When psycopg2.connect fails, raise PostgresConnectionError."""
    # Arrange
    mock_conn = MagicMock()
    # Mock psycopg2.connect żeby rzucał OperationalError (np. DB niedostępny)
    mocker.patch(
        'src.load.postgres.psycopg2.connect',
        side_effect=psycopg2.OperationalError("could not connect to server"),
    )

    # Act + Assert
    with pytest.raises(PostgresConnectionError) as exc_info:
        with postgres_loader.connection() as conn:
            pass  # nie dotrzemy tu

    # Sprawdź że message zawiera informację
    assert "Failed to connect" in str(
        exc_info.value) or "connection error" in str(exc_info.value).lower()


def test_connection_rollbacks_on_exception_inside_with(postgres_loader, mocker):
    """Exception inside `with loader.connection()` should trigger rollback."""
    # Arrange
    mock_conn = MagicMock()
    mocker.patch('src.load.postgres.psycopg2.connect', return_value=mock_conn)

    # Act
    with pytest.raises(ValueError, match="test boom"):
        with postgres_loader.connection() as conn:
            raise ValueError("test boom")  # symulujemy crash w środku

    # Assert: rollback został wywołany, commit NIE
    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
    mock_conn.close.assert_called_once()  # close w finally zawsze się wywołuje
