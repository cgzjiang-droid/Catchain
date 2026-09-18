import pytest

from catchain.config import ConfigurationError, RuntimeConfig
from catchain.storage.postgres import ProductionDatabase


def test_production_database_rejects_sqlite_before_connecting() -> None:
    config = RuntimeConfig(
        environment="production",
        database_url="sqlite+pysqlite:///data/catchain.sqlite",
        object_store_uri="s3://bucket",
    )

    with pytest.raises(ConfigurationError, match="database_url"):
        ProductionDatabase.from_config(config)


def test_postgres_database_config_is_lazy_until_connection() -> None:
    config = RuntimeConfig(
        environment="production",
        database_url="postgresql+psycopg://catchain:secret@db/catchain",
        object_store_uri="s3://bucket",
    )

    database = ProductionDatabase.from_config(config, create_engine=False)

    assert database.database_url == config.database_url

