# Security checklist

Use as prompts for tracing, not as a list to tick through. Each item needs
a concrete flow in this change to become a finding.

## Authentication and authorization

- The check sits at the point of the privileged action, not only upstream.
- Every route, job, consumer or entry point that reaches the same
  privileged operation enforces it, including older and internal ones.
- A component acting for a caller checks the caller's authority, not its
  own (confused deputy). Tokens and elevated context do not leak across
  threads, queues or process boundaries.
- Session, token and password handling: expiry, rotation, comparison in
  constant time, reset and recovery flows.

## Injection and untrusted input

- Untrusted input reaching SQL, shell, template, path, URL, deserializer,
  regex, header or log sinks without validation or parameterization.
- Validation or sanitization still holds where the value is used, not only
  where it was checked (decode, normalize or concatenate after the check).
- Outbound requests built from user input (SSRF); redirects and open
  redirects; file uploads, archive extraction and path traversal.

## Secrets and crypto

- Credentials, keys or tokens in code, config, fixtures, logs, errors or
  client bundles.
- Weak or home-made primitives, fixed IVs or salts, predictable randomness
  for security use, disabled certificate or signature checks, algorithm
  confusion.

## Trust boundaries and data exposure

- Data crossing from a less to a more trusted context: client to server,
  tenant to tenant, user to admin, service to service.
- Responses, errors and logs exposing more than the caller may see; mass
  assignment; missing tenant scoping on a query.
- CORS, CSRF, cookie flags and security headers when the change touches
  them.

## Dependencies and supply chain

- A new or upgraded dependency: what it adds, its source, and whether the
  version is pinned and from the expected registry.
- Lockfile changes that add packages the manifest change does not explain.
- Mutable references in build and CI (unpinned actions or images), widened
  workflow permissions, install scripts, and secrets exposed to code from
  an untrusted pull request.
