# omail

English | [简体中文](README.zh-CN.md)

A single-file, zero-dependency command-line tool for Microsoft 365 mailboxes: full mail management (read, search, digest, attachments, send/reply/mark/move/delete) and calendar management (list, create, update, delete), all through the Outlook REST API v2.0.

**Works with** Microsoft 365 tenants — the supported and tested path is the 21Vianet (China) cloud; a legacy global-cloud profile is included (see *Cloud support status* below). **No tenant admin consent required** — it uses the device-code flow with the Microsoft Office first-party application's pre-consented permissions; you sign in once with your own account.

## Cloud support status

- **21Vianet (China) — supported.** Default cloud. Outlook REST API v2.0 at `partner.outlook.cn`; this is the configuration the tool is developed and tested against.
- **Global cloud — legacy, provided as-is.** The `global` profile targets the Outlook REST API v2.0 at `outlook.office365.com`. Microsoft has deprecated that API on the global cloud in favor of Microsoft Graph and is retiring it, so this profile may stop working at any time and is **not** verified against current global endpoints. Treat it as a starting point, not a supported configuration.
- A Microsoft Graph backend is a possible future direction; it is not part of this version, and the no-admin-consent device-code model is the reason the current design stays on the v2.0 surface where it remains available.

## Requirements

- Python 3.9+ (standard library only; `certifi` is optional and used when a Python distribution lacks a CA bundle)
- Network access to your cloud's sign-in and API endpoints (honours `https_proxy` / `HTTPS_PROXY` if set)

If sign-in fails with a local certificate verification error, set `SSL_CERT_FILE` to a trusted CA bundle. When the optional `certifi` package is installed, `omail` uses it automatically if the Python installation has no usable default CA bundle.

## Quick start

```bash
chmod +x bin/omail
bin/omail auth --email you@yourcompany.com
# open the printed URL, enter the device code, sign in with your company account
bin/omail doctor   # health check: prints your account and inbox counts
```

Global Microsoft 365 (legacy profile, see *Cloud support status*): add `--cloud global`. Your tenant ID is auto-discovered from your email domain (override with `--tenant <guid>` if ever needed).

## How it works

- **Service model.** Everything runs against the Outlook REST API v2.0 on the Microsoft 365 sovereign cloud operated by 21Vianet (`partner.outlook.cn`). No IMAP, EWS, or Graph dependency — one API surface for mail, calendar, and contacts.
- **Auth model.** OAuth 2.0 device flow using the Microsoft Office first-party client. That choice is deliberate: it needs no app registration and no tenant-admin consent, which is what makes the tool usable inside organizations where custom app registrations are not approved. The refresh token is stored locally with mode 600 and rotated on every refresh; re-authentication is one interactive `reauth` command.
- **Transport.** HTTP goes through a manual CONNECT tunnel because standard library proxy handling is unreliable behind some corporate egress proxies.
- **Safety model.** Reads print JSON and change nothing. Writes (`send`, `reply`, `delete`, `event-create`, …) accept `--dry-run` (validate and preview, no API call) and are journal-guarded, so a retried write cannot silently duplicate a sent mail or a created event.
- **Why a CLI.** After one sign-in, every command is non-interactive and machine-readable — the shape an AI agent (or a cron job) needs to work a mailbox reliably.

## Commands

Read-only:

| Command | Purpose |
|---|---|
| `doctor` | Health check + inbox counts |
| `folders` | Folders with counts |
| `list [--folder NAME] [--unread] [--top N]` | Message list (default: inbox) |
| `search "keywords" [--top N]` | Mailbox-wide search (subject + body) |
| `read <id> [--body-max N]` | Read one message; `--body-max N` truncates the body (`body_truncated` flag in output) |
| `attachments <id>` / `attachment-get <id> <attId> <path>` | List / download attachments |
| `digest <ISO-time>` | Unread mail since a timestamp (built for morning digests) |
| `calendar [--days N]` / `calendars` / `event <id>` | Calendar window / calendar list / one event (times in UTC) |
| `contacts [--search KW] [--top N]` | Personal contacts (name/email/company/title/department; no phone fields) |
| `find KEYWORD [--top N]` | People lookup: global address book search merged with personal contacts (results carry a `sources` tag); CJK full names occasionally miss in the directory — an e-mail prefix is the most reliable query |

Writes (irreversible — confirm before running in automation):

| Command | Purpose |
|---|---|
| `send --to A [--cc C] --subject S --body B \| --body-file F [--attach f1,f2]` | Send mail, attachments supported |
| `reply <id> --body B` | Reply (auto `RE:`) |
| `mark <id> --read \| --unread` | Mark read/unread (exactly one flag required) |
| `move <id> --folder NAME` | Move (message Id changes afterwards; re-locate via search/list) |
| `delete <id>` | Delete; deleting again in Deleted Items is permanent |
| `event-create --subject S --start ISO --end ISO [--tz TZ] [--location L] [--body B] [--attendees a@x,b@y] [--calendar ID]` | Create event; times are local wall-clock, `--tz` is a Windows time-zone name (default `China Standard Time`); **attendees receive invitations** |
| `event-update <id> [same fields]` | Update an event (only the fields you pass) |
| `event-delete <id>` | Delete an event (attendees get a cancellation) |

All output is JSON. List commands follow `@odata.nextLink` automatically, so large result sets are never silently truncated.

## Safety design for writes

- **`--dry-run` preview**: every write command accepts `--dry-run` — validates arguments and prints the exact action as JSON, without fetching a token or calling the API.
- **Validation up front**: required fields, email formats, ISO times and ordering, attachment/body file existence are checked before any request; failures are `usage` errors (exit code 64).
- **Idempotency**: the transport layer never blindly retries a write — if a response is lost after a request was sent, you get `ambiguous_outcome` (exit code 3) and should verify before re-running. On top of that, `send` and `event-create` keep a local journal (`write_journal.json`, next to the token store): an identical write within 10 minutes is refused; pass `--force` once you have verified the first one really did not happen.

## Tokens & security

- After sign-in, a refresh token is stored in `token_store.json` (auto-rotated, file mode 600). Location: `$OMAIL_HOME` if set, else next to the package, else `~/.omail/`.
- **A refresh token is as sensitive as your password.** Never commit it, share it, or copy it between machines — just run `auth` again on the new machine. (The included `.gitignore` already excludes it.)
- If commands fail with `token_invalid` (exit code 2), re-run `omail auth --email ...` and enter a fresh device code.

## Known limitations

- Authorisation depends on your tenant having the Office first-party app's OutlookService permissions pre-consented (true for most M365 tenants). If sign-in fails with AADSTS65002, this route is blocked in your tenant — contact your admin; do not try to work around it with custom app registrations.
- Uses the Outlook REST API v2.0 (not Microsoft Graph); endpoints for both clouds are built in.
- `calendar` returns UTC times; convert for display. After `event-update`, the service may present start/end in UTC — the actual moment is unchanged.
- Event deletion is a hard delete (no recycle bin for events).

## Tests

```bash
python3 -m unittest discover -s tests -v   # 39 tests, fully offline, no account needed
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Current version: **v1.2.2**.

## License

MIT — see [LICENSE](LICENSE).
