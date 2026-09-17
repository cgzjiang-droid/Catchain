# CATchain repository guidance

- Follow the approved architecture in docs/superpowers/specs/2026-09-09-catchain-redesign.md.
- Update docs/PROJECT_PROGRESS.md, applicable plans, learning notes and docs/USAGE_ZH.md
  whenever the implemented behavior or next checkpoint changes.
- Validate relevant changes with the existing venv and run Ruff before publishing.
- Publish authorized completed code, progress, future plans and usage documentation
  to https://github.com/cgzjiang-droid/Catchain. Do not publish raw PDFs, runtime
  databases, private output, environment secrets or caches.
- Contributor identity requested by the owner: cgzjiang-droid,
  225338530+cgzjiang-droid@users.noreply.github.com. Configure identity for this
  repository only; do not modify global Git identity or rewrite local development history.
- The first public release is a source snapshot because old local commits used an
  unlinked machine email. Keep original local history intact. Publication checkout:
  /Users/jiangchunlin/Documents/ChatGPT/学习/Catchain-github-publish.
- Later publication uses that checkout: inspect/fetch remote changes first, update
  the tested tracked source snapshot, inspect the diff, commit and push normally.
  Preserve remote work; never force-push or overwrite unrelated changes. Do not
  claim synchronization until the remote commit has been verified.
- If GitHub authentication cannot write the repository, prepare the tested snapshot
  and report the actual authentication blocker. Never request or commit a token.
