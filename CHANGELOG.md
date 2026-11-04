# Changelog

## v1.2.2 (2026-11-04)

- **New read-only commands `contacts` / `find`**: `contacts [--search KW] [--top N]` lists personal contacts (`/me/contacts`; name/email/company/title/department — phone fields are not selectable in REST v2.0 and return HTTP 400). `find KEYWORD [--top N]` looks people up in the global address book (`/me/people?$search=`) and merges personal-contact matches, tagging each result with its `sources`; an unquoted retry covers tenants that reject the quoted search form. Contact matching tolerates CJK surname/given-name ordering (a contact shown as "given-name surname" is found by "surname given-name"); the character-set fallback is restricted to short CJK names so Latin queries do not false-positive.
- **Tests**: 39 offline cases (8 new for contacts/find views, matching, merging, and argument guards).


## v1.2.1 (2026-11-04)

- **Portable TLS certificates**: use an optional `certifi` CA bundle when the Python installation has no usable default bundle; explicit `SSL_CERT_FILE` / `SSL_CERT_DIR` settings remain respected.
- **`--body-max` edge cases**: `read --body-max 0` now returns an empty body with `body_truncated: true`; negative and non-numeric values return a clear usage error.
- **CI**: run the offline test suite on Ubuntu, macOS, and Windows across supported Python versions.

## v1.2.0 (2026-11-04)

- **Automatic pagination**: `list` / `search` / `folders` / `calendar` / `calendars` follow `@odata.nextLink` until the requested total is collected — no more silent truncation at one server page.
- **Idempotency protection for writes**:
  - The transport layer no longer blindly retries writes: connection-stage failures may retry, but a failure after the request was sent raises `ambiguous_outcome` (exit code 3) instead of risking a duplicate send / duplicate event.
  - `send` / `event-create` keep a local journal (`write_journal.json`): an identical write that completed — or whose outcome is unknown — within 10 minutes is refused; `--force` overrides after manual verification.
- **Validation & preview**: all write commands validate up front (required fields, email format, ISO time format and ordering, attachment/body file existence; missing positionals are clear `usage` errors, exit 64) and support `--dry-run` (validate + print the action JSON; no token fetch, no API call, no journal write).
- **Unit tests**: `tests/` with 28 offline stdlib-unittest cases (parsing, proxy env vars, tenant discovery, pagination, validation, dry-run, mark guard, journal, duplicate-send blocking, retry policy, body truncation).

## v1.1.1 (2026-11-04)

- Proxy environment variables are recognised in both cases (previously only lowercase `https_proxy`, contradicting the docs).
- `read --body-max` actually implemented (previously documented but ignored); output gains `body_truncated`.
- `mark` with neither or both of `--read`/`--unread` is now a usage error (previously a missing flag silently marked the message unread).

## v1.1.0 (2026-11-04)

- Calendar writes: `calendars` / `event-create` / `event-update` / `event-delete`, verified end-to-end (create → update → delete, no residue). Mail + calendar management complete.

## v1.0.0 (2026-11-04)

- First release: full mail toolset (list/search/read/attachments/digest/send/reply/mark/move/delete) and calendar reads; tenant auto-discovery from the email domain; Microsoft 365 global + 21Vianet clouds; adaptive token-store location. Verified end-to-end on 21Vianet (including byte-identical attachment round-trip); global cloud configuration built in, not yet verified.
