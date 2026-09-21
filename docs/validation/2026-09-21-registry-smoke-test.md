# Registry online smoke test — 2026-09-21

This is a read-only transport check. It does not create projects, download a
30G dataset, or treat an inaccessible endpoint as an empty Registry.

The smoke classifier records four separate outcomes:

- `ok`: a bounded HTTP 2xx response contains valid JSON data;
- `endpoint_mismatch`: the URL returns an HTML application shell or another
  content type instead of the expected data;
- `blocked`: the endpoint explicitly refuses the request (for example 403);
- `not_found`: the endpoint or legacy path returns 404 or an invalid-page
  response.

## Observed responses

| Registry | Probe | HTTP | Content type | CATchain result | Evidence |
| --- | --- | ---: | --- | --- | --- |
| ACR | `https://acr2.apx.com/` | 200 | `text/html` | `not_found / html_not_found` | Body says `Invalid page` |
| ACR | `https://acr2.apx.com/mymodule/Project_ViewFile.asp?id1=729` | 404 | `text/html` | `not_found / http_404` | Legacy document path no longer resolves |
| Verra/VCS | `https://registry.verra.org/uiapi/resource/resourceSummary/7` | 200 | `text/html` | `endpoint_mismatch / html_instead_of_data` | Response is the SPA HTML shell, not JSON |
| Gold Standard | `https://assurance-platform.goldstandard.org/api/public/project-documents/7` | 403 | `text/html` | `blocked / http_403` | Server explicitly denied the unauthenticated request |

The probes were executed with a bounded GET and a CATchain user agent. The
responses prove transport behavior only; they do not prove that a Registry has
no documents. The ACR and Verra parsers therefore remain fixture-tested, while
the live adapters stay explicitly unconfigured until their current public
discovery/download contract is verified.

## Decision and next gate

The sync service must persist the classified failure (`http_403`, `http_404`,
`html_instead_of_data`, or `network_error`) with the checkpoint rather than
turning it into an empty successful page. This is the acceptance gate for the
online transport layer.

The next live-sync gate is one authenticated or officially documented public
fixture per Registry, followed by a real small sample. Until that evidence is
available, no live Registry run is marked production-ready and no 30G ingest is
claimed.

Official starting points for re-checking the current contracts:

- [ACR Registry](https://acrcarbon.org/acr-registry/)
- [Verra Registry overview](https://verra.org/registry/overview/)
- [Gold Standard project developer resources](https://www.goldstandard.org/project-developer-resources)
