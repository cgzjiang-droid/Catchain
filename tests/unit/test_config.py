import pytest

from catchain.config import ConfigurationError, RuntimeConfig


def test_production_config_requires_postgres_and_remote_object_storage() -> None:
    config = RuntimeConfig(
        environment="production",
        database_url="postgresql+psycopg://catchain:secret@db/catchain",
        object_store_uri="s3://catchain-raw",
    )

    assert config.production_violations() == ()


@pytest.mark.parametrize(
    ("database_url", "object_store_uri", "expected"),
    [
        ("sqlite+pysqlite:///data/catchain.sqlite", "s3://bucket", "database_url"),
        ("postgresql+psycopg://u:p@db/catchain", "file:///data/raw", "object_store_uri"),
    ],
)
def test_production_config_rejects_development_storage(
    database_url: str, object_store_uri: str, expected: str
) -> None:
    config = RuntimeConfig(
        environment="production",
        database_url=database_url,
        object_store_uri=object_store_uri,
    )

    assert any(expected in violation for violation in config.production_violations())
    with pytest.raises(ConfigurationError, match=expected):
        config.require_production_safe()


def test_development_config_can_use_sqlite_and_local_store() -> None:
    config = RuntimeConfig(
        environment="development",
        database_url="sqlite+pysqlite:///data/catchain.sqlite",
        object_store_uri="file:///data/raw",
    )

    config.require_production_safe()

