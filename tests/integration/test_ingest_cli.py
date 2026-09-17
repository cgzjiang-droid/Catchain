from pathlib import Path

from sqlalchemy import func, select
from typer.testing import CliRunner

from catchain.cli import app
from catchain.storage.database import create_sqlite_engine, document_versions


def test_ingest_local_reports_and_persists_content_deduplication(tmp_path: Path) -> None:
    local_file = tmp_path / "project.pdf"
    local_file.write_bytes(b"licensed test fixture")
    database_path = tmp_path / "catchain.sqlite"
    raw_root = tmp_path / "raw"
    arguments = [
        "ingest",
        "local",
        str(local_file),
        "--registry",
        "verra",
        "--project-id",
        "VCS-1234",
        "--source-url",
        "https://registry.example/projects/1234/pdd.pdf",
        "--document-type",
        "project_description",
        "--database",
        str(database_path),
        "--raw-root",
        str(raw_root),
    ]
    runner = CliRunner()

    first = runner.invoke(app, arguments)
    second = runner.invoke(app, arguments)

    assert first.exit_code == 0
    assert "Stored new document version" in first.stdout
    assert second.exit_code == 0
    assert "Reused existing document version" in second.stdout

    engine = create_sqlite_engine(database_path)
    with engine.connect() as connection:
        version_count = connection.scalar(select(func.count()).select_from(document_versions))
    assert version_count == 1
