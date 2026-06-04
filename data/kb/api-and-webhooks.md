# API and Webhooks

The Nimbus public REST API lets you read and write projects, tasks, comments, and
members programmatically. The API is available on the Growth and Enterprise plans.

**Authentication.** Create an API token under **Settings → Developer → API
tokens**. Send it as a bearer token: `Authorization: Bearer <token>`. Tokens
inherit the permissions of the member who created them; create a token under a
service account for automation.

**Base URL and versioning.** All endpoints live under `https://api.nimbus.example/v1`.
We version in the path and never make breaking changes within a version.

**Webhooks.** Configure webhooks under **Settings → Developer → Webhooks** to
receive real-time `POST` callbacks when events happen — `task.created`,
`task.updated`, `task.completed`, `comment.created`, and `member.added`. Each
delivery is signed with an HMAC-SHA256 signature in the `X-Nimbus-Signature`
header so you can verify authenticity. Failed deliveries are retried with
exponential backoff for up to 24 hours.

**Pagination** uses cursor-based `?cursor=` parameters; responses include a
`next_cursor`. For request limits, see *API Rate Limits*.
