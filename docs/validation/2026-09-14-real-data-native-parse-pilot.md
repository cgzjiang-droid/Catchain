# Real-data native PDF parsing pilot — 2026-09-14

## Purpose

Validate the current PyMuPDF adapter against locally available CATchain source
documents before implementing OCR fallback. The source PDFs were read in place;
they were not copied into the repository or modified.

This run measures native-text parseability. It does not measure field-extraction
accuracy, evidence accuracy, or LLM confidence.

## Sample

One core document was selected from each locally available project. PDD or project
plan documents were preferred where available.

| Registry | Project | Selected file | Pages | Pages with fewer than 80 non-whitespace characters |
| --- | --- | --- | ---: | --- |
| ACR | p_ACR125 | `MRV_SEESA_2008_1.pdf` | 18 | 11, 14, 15 |
| ACR | p_ACR129 | `MRV_Tecnosol_2007_1.pdf` | 19 | 12, 15, 16, 17 |
| ACR | p_ACR177 | `Monjolinho_Energetica_GHG_Final.pdf` | 105 | 4, 15, 16, 22, 36, 40, 100, 103 |
| ACR | p_ACR191 | `Ms_Renovaveis_Project_Plan_Final_.pdf` | 71 | 4, 17, 21, 36, 42, 45, 61, 65 |
| ACR | p_ACR224 | `Santos_Energia_Final.pdf` | 76 | 51 |
| GS | p_GS1003 | `Degirmen_HPP-Project-Annual-Report_....pdf` | 6 | none |
| GS | p_GS1012 | `PDD_07-05-12_....pdf` | 63 | 21, 54, 56, 57, 58, 59, 60 |
| VCS | p_VCS1 | `PDD_7.25MW_Wind_Aruppukottai_-_India_fileid_7.pdf` | 47 | 44 |
| VCS | p_VCS6 | `Muling_Daimagou_PDD_phase_2_v2_0_fileid_84.pdf` | 39 | none |
| VCS | p_VCS7 | `Muling_Daimagou_PDD_phase_1_v2_0_fileid_79.pdf` | 39 | none |
| VCS | p_VCS10 | `VCS_PD_V04_fileid_100.pdf` | 44 | none |

## Results

- 11 of 11 documents opened and parsed successfully.
- 527 pages were processed from 20,209,698 bytes of source PDFs.
- 32 pages had fewer than 80 non-whitespace native-text characters.
- 3 pages had no native text: p_ACR177 page 15, p_ACR191 page 36, and
  p_ACR224 page 51.
- No page exceeded a 2% Unicode replacement-character ratio.
- The run produced only a 16 KB JSON/CSV result before diagnostic page images.

The three empty-text pages were rendered and visually checked. All three are blank
pages, so sending them to OCR would waste processing time and could create false
text. A text-count threshold alone cannot distinguish a blank page from a scanned
page that contains meaningful content.

## Product decision for OCR routing

The OCR policy needs at least three outcomes:

1. Keep native text when it passes deterministic quality checks.
2. Send a low-text page to OCR when the rendered page contains meaningful visual
   content.
3. Preserve a genuinely blank page as blank and record that decision.

The implemented rendered-page inspection classified the 32 low-text pages into 29
pages with meaningful visual content and 3 blank pages. Only the 29 visual-content
pages are OCR candidates. This classification is a routing decision; it does not
prove that every candidate contains readable text or that OCR will be accurate.

The local machine does not currently have a `tesseract` executable. The production
adapter was therefore verified with a deterministic fake executable and with the
real missing-tool path. The latter returns an actionable `OcrToolUnavailableError`
instead of producing an empty parsed result.

## Reproducibility artifacts

The local ignored directory `data/parsed/pilot-2026-09-14/` contains:

- `manifest.csv`: one row per selected source document;
- `report.json`: SHA-256, parser version, page counts, quality measurements, and
  source paths;
- `page-checks/`: rendered images used to inspect the three empty-text pages.

Absolute source paths stay in the ignored local report and are not committed.
