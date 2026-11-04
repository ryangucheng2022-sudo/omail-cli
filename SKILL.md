---
name: omail-outlook
description: Manage an Outlook / Microsoft 365 mailbox programmatically with the omail CLI (global + 21Vianet): unread checks, search, message bodies, attachments, morning digests, calendars, and creating/updating/deleting events. Use when the user asks you to handle their company (Outlook) mailbox or calendar.
---

# omail — rules for agents

Tool: `bin/omail` (single-file Python, standard library only). Read the bundled README.md for the full command table.

## First-time setup

1. `omail auth --email <user's company email>` (add `--cloud global` for global Microsoft 365). The command prints a device code and a sign-in URL — relay both to the user verbatim; they complete sign-in in their browser. The command polls until success and stores the token.
2. `omail doctor` to verify: account + inbox counts mean you are connected.

## Red lines

- **Before any write, restate it in full and get the user's confirmation**: `send` (recipients/cc/subject/body summary/attachment list), `reply`, `delete`, `move`, batch `mark`, and the calendar writes `event-create` / `event-update` / `event-delete` (subject/time/location/attendees). Exception: a single `mark` the user explicitly named in the same instruction may run directly. Running `--dry-run` first to produce a normalised preview for the user is encouraged.
- **Creating an event with attendees sends them invitations**; deleting such an event sends cancellations. Treat both like sending mail — confirm first.
- On `ambiguous_outcome` (exit code 3), **never blindly re-run**: verify whether the write landed (Sent Items / calendar) and only then retry with `--force`. The same applies when the idempotency journal blocks a duplicate `send`/`event-create`.
- Read-only commands (doctor/folders/list/search/read/attachments/digest/calendar/calendars/event) may run without asking.
- For digests/summaries use metadata + preview only; do not open full bodies.
- The token file `token_store.json` is password-equivalent: never print it, paste it, or include it in reports.

## Troubleshooting

- `token_invalid` (exit code 2): do not retry in a loop. Run `omail auth --email <address>` and give the user the new device code.
- After `move`, the message Id changes — re-locate with `search`/`list` before further operations.
- `search` covers the whole mailbox; `list`/`digest` cover the inbox only (some system mail is delivered elsewhere).
- Calendar times are UTC; convert to the user's time zone when reporting.
