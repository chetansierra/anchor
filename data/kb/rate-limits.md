# API Rate Limits

The Nimbus API enforces rate limits to keep the service fast and fair for everyone.
Limits are applied per API token.

**Default limits:**

- **Growth plan:** 120 requests per minute, burst up to 200.
- **Enterprise plan:** 600 requests per minute, burst up to 1,000, with higher
  limits available on request.

**Rate limit headers.** Every API response includes:

- `X-RateLimit-Limit` — your ceiling for the current window.
- `X-RateLimit-Remaining` — requests left in the window.
- `X-RateLimit-Reset` — seconds until the window resets.

**When you exceed the limit**, the API returns HTTP **429 Too Many Requests** with
a `Retry-After` header telling you how long to wait. Back off and retry after that
interval; clients should implement exponential backoff.

**Webhook deliveries** and bulk export jobs do not count against your API rate
limit. Writes that create many objects at once (bulk endpoints) count as a single
request but have a lower per-minute ceiling.

If you consistently hit the limit, batch your reads, cache responses, or contact
sales about a higher tier.
