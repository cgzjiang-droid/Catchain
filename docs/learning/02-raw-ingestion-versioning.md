# Lesson 2: Raw Ingestion, Hashing, and Versioning

## The product problem

CATchain cannot produce defensible carbon-project data unless it can prove which source file was processed. Registry files may be downloaded repeatedly, renamed, replaced at the same URL, or published in corrected versions. The Raw layer therefore preserves original bytes before parsing, extraction, validation, or scoring begins.

## The user flow

```text
Local source file + Registry metadata
→ compute SHA-256 from the bytes
→ store immutable Raw content
→ save source and version metadata in SQLite
→ reuse identical content or create a new content version
```

This is a deterministic Workflow. An Agent or LLM would make the identity and audit path less reliable without adding useful judgment.

## Inputs

The local-import command requires:

- local file path;
- Registry and project identifier;
- original source URL;
- document type;
- optional declared version and content type.

The command also accepts a Raw root and SQLite path so tests and runtime environments can remain isolated.

## Outputs

Each successful import reports:

- whether a new version was stored or an existing version reused;
- SHA-256;
- byte size;
- immutable Raw path.

SQLite links this content to a `SourceDocument` and `DocumentVersion`. The Raw path is derived from the hash, while the database preserves the business context needed to understand the file.

## Three different identities

`SourceDocument ID` identifies a logical Registry document. `SHA-256` identifies exact file bytes. `DocumentVersion ID` identifies one version record that connects the two.

File names cannot replace these identities. Two identical files can have different names, and two different files can both be named `project.pdf`.

## Deduplication and idempotency

Importing the same content twice returns the first `DocumentVersion` and leaves one Raw blob and one version row. This is idempotent behavior: retrying the same request does not create duplicate business state.

If the file bytes change, the SHA-256 changes. CATchain stores a second Raw blob and creates a second `DocumentVersion`; it never overwrites the first version.

## What SHA-256 proves

SHA-256 provides a stable content fingerprint. It helps answer:

- Have these exact bytes already been stored?
- Did a file change between downloads?
- Which exact bytes produced an extracted result or evidence reference?

SHA-256 does not prove that a document is authentic, current, correct, complete, or safe. Those claims require source validation, version comparison, domain rules, and sometimes human review.

## Why SQLite is behind a repository

The ingestion service calls a document repository rather than embedding SQL in the workflow. This keeps the product behavior stable if the MVP later replaces SQLite. It also ensures database rows are reconstructed as validated Pydantic domain models.

Alembic migrations version the database structure. Future schema changes become reviewable upgrades instead of unrecorded manual edits.

## Failure modes

- Missing, directory, or empty input: reject the import.
- Same source and same content: reuse the existing version.
- Same source and new content: create a new version.
- Same source ID with conflicting source metadata: reject and investigate identity.
- Database or filesystem failure: fail explicitly; do not claim the import completed.

## Product-manager acceptance criteria

The feature is acceptable when:

1. stored bytes match input bytes;
2. repeated content creates no duplicate version;
3. changed content preserves both versions;
4. source metadata can be reconstructed from SQLite;
5. failures are visible rather than converted into empty results.

Useful product metrics later include duplicate rate, new-version rate, failed-import rate, bytes stored, and time per import.

## Interview questions

**Why not identify documents by filename?** Filenames are mutable and non-unique; CATchain separates logical identity from exact content identity.

**Why preserve old versions?** Extracted facts and decisions must remain traceable to the exact source version used at that time.

**Why is hashing deterministic software?** The same bytes always produce the same result, so an LLM adds uncertainty without providing useful interpretation.

**Does matching SHA-256 prove a date is correct?** No. It proves byte equality only; correctness still requires evidence and validation.

## Minimum explanation

> CATchain first preserves original bytes in an immutable Raw layer. SHA-256 identifies exact content, prevents duplicate storage, and reveals changed versions. SQLite stores the logical document and version history through a repository. Re-importing identical content reuses the existing version, while changed content creates a new version without deleting history. This makes every later extraction traceable to the exact source bytes.
