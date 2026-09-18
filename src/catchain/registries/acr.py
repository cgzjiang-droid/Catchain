"""ACR response parsing retained from the audited legacy collector."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin

from catchain.domain import DocumentType, Registry
from catchain.registries.base import RemoteDocument


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._href = dict(attrs).get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None


def parse_acr_links(
    *, project_id: str, discovery_url: str, html: str, discovered_at
) -> tuple[RemoteDocument, ...]:
    """Extract document links whose URL or visible label identifies a PDF."""

    parser = _LinkParser()
    parser.feed(html)
    documents: list[RemoteDocument] = []
    for index, (href, title) in enumerate(parser.links, start=1):
        if ".pdf" not in href.lower() and ".pdf" not in title.lower():
            continue
        documents.append(
            RemoteDocument(
                registry=Registry.ACR,
                project_id=project_id,
                document_id=f"acr-{project_id}-{index}",
                document_type=DocumentType.OTHER,
                title=title or href.rsplit("/", 1)[-1],
                url=urljoin(discovery_url, href),
                discovered_at=discovered_at,
            )
        )
    return tuple(documents)

