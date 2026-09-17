from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_document_tables(tmp_path: Path) -> None:
    repository_root = Path(__file__).parents[3]
    config = Config(repository_root / "alembic.ini")
    database_path = tmp_path / "migrated.sqlite"
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")

    command.upgrade(config, "head")

    table_names = set(inspect(create_engine(f"sqlite+pysqlite:///{database_path}")).get_table_names())
    assert table_names == {
        "alembic_version",
        "document_versions",
        "parsed_documents",
        "parsed_pages",
        "source_documents",
    }
