from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from catchain.storage.database import create_sqlite_engine, metadata


def test_initial_migration_creates_document_tables(tmp_path: Path) -> None:
    repository_root = Path(__file__).parents[3]
    config = Config(repository_root / "alembic.ini")
    database_path = tmp_path / "migrated.sqlite"
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")

    command.upgrade(config, "head")

    table_names = set(
        inspect(create_engine(f"sqlite+pysqlite:///{database_path}")).get_table_names()
    )
    assert table_names == {
        "alembic_version",
        "document_versions",
        "parsed_documents",
        "parsed_pages",
        "source_documents",
        "processing_runs",
        "validation_reports",
        "fact_candidates",
        "candidate_evidence",
        "review_decisions",
        "canonical_facts",
        "review_requests",
        "canonical_heads",
        "evaluation_results",
        "stored_objects",
    }
    engine = create_sqlite_engine(database_path)
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), metadata) == []


def test_fact_migration_preserves_existing_sources_and_downgrades(tmp_path):
    root = Path(__file__).parents[3]
    config = Config(root / "alembic.ini")
    path = tmp_path / "existing.sqlite"
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{path}")
    command.upgrade(config, "0002_parsed_documents")
    engine = create_sqlite_engine(path)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO source_documents VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("original", "verra", "VCS1", "https://example.org/a.pdf", "other", None, "2026-09-17"),
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT source_document_id FROM source_documents"
            ).scalar_one()
            == "original"
        )
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    command.downgrade(config, "0002_parsed_documents")
    assert "fact_candidates" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT source_document_id FROM source_documents"
            ).scalar_one()
            == "original"
        )
