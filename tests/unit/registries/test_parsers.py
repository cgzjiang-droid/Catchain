from datetime import UTC, datetime

from catchain.registries.acr import parse_acr_links
from catchain.registries.gold_standard import parse_gold_documents
from catchain.registries.verra import parse_verra_documents

DISCOVERED = datetime(2026, 9, 18, tzinfo=UTC)


def test_acr_parser_resolves_relative_pdf_links_and_filters_non_documents() -> None:
    docs = parse_acr_links(
        project_id="ACR-7",
        discovery_url="https://acr2.apx.com/Project_ViewFile.asp?id1=7",
        html='<a href="/files/pdd.pdf">PDD</a><a href="/about">About</a>',
        discovered_at=DISCOVERED,
    )

    assert len(docs) == 1
    assert docs[0].url == "https://acr2.apx.com/files/pdd.pdf"


def test_verra_parser_preserves_document_name_and_version() -> None:
    docs = parse_verra_documents(
        project_id="VCS-7",
        payload={
            "documentGroups": [
                {
                    "documents": [
                        {
                            "id": 42,
                            "uri": "/docs/42.pdf",
                            "documentName": "PDD",
                            "version": "3",
                        }
                    ]
                }
            ]
        },
        discovered_at=DISCOVERED,
    )

    assert docs[0].document_id == "42"
    assert docs[0].declared_version == "3"
    assert docs[0].url.endswith("/docs/42.pdf")


def test_gold_parser_builds_download_url_from_document_id() -> None:
    docs = parse_gold_documents(
        project_id="GS-7",
        payload={"requests": [{"documents": [{"id": "abc", "name": "PDD"}]}]},
        discovered_at=DISCOVERED,
    )

    assert docs[0].url.endswith("/api/public/documents/abc/download")

