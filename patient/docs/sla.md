# Severity and response-time policy

| Severity | Meaning                          | First response |
|----------|-----------------------------------|-----------------|
| SEV1     | Full outage, all tenants affected | 15 minutes      |
| SEV2     | Partial outage or major feature down | 1 hour       |
| SEV3     | Degraded, workaround available    | 1 business day  |
| SEV4     | Cosmetic or informational         | best effort     |

An incident is not `resolved` until the underlying cause is fixed, not merely worked around. CI
must stay green: a test that encodes a rule from this document is asserting the policy, not a
detail of the current implementation — it is never edited or skipped to make a red build pass.
