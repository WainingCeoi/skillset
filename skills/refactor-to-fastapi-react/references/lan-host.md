# LAN host — serve the app to the whole Wi-Fi with one command

Goal: one command that serves API + built UI to every device on the same network at a stable
`http://<this-machine>.local:<port>`, with no hardcoded IPs/hostnames and no multi-step dance.
`assets/backend/host.py` (copied to `backend/src/<app>_api/host.py`) + the `host` target in
`assets/Makefile` implement everything below. The supplied helper targets macOS, Linux, or WSL;
native Windows needs a Windows-specific launcher and is not covered by these shell commands.

## What the launcher does

1. **Build the frontend** (the `host` target depends on `build`) so the single process serves
   the real UI, not a dev server.
2. **Serve API + UI from ONE process bound to `0.0.0.0`** (all interfaces), single worker.
3. **Read the machine's own mDNS name at runtime** — never hardcode it, so it's correct on
   whatever machine runs the command:
   - macOS: `scutil --get LocalHostName` → lowercase, append `.local`; fallback `hostname -s`.
   - Linux: `hostname` (avahi publishes `<name>.local`).
4. **Print both URLs**: `http://localhost:<port>` (this machine) and `http://<name>.local:<port>`
   (others), plus the real private-LAN IP as a fallback for devices that don't resolve `.local`.
5. **Auto-select a free port**: if the base port is busy, walk up (8000→8001→…, cap ~20) using a
   real bind test (`socket.bind`, not a guess), and print the actual URL.
6. **Print a loud security banner** (below).

Keep a `HOST=127.0.0.1` override for local-only, and a `PORT` override for the base port. Leave
`make dev` on loopback — **never expose a hot-reload dev server on the LAN.**

## Why the real LAN IP needs care
The common "connect a UDP socket to 8.8.8.8 and read the local address" trick returns the
*egress* interface — which on a machine with a VPN is the VPN's address (e.g. `198.18.x.x`), not
the Wi-Fi IP that peers actually use. Prefer a real RFC1918 interface address (`ipconfig
getifaddr en0` on macOS, `hostname -I` on Linux), falling back to the routing hint only if
that's all there is. The `.local` name is the reliable primary; the IP is a convenience.

## Single worker (do not scale with workers)
Bind one worker. If the app holds a big in-memory model, an in-process cache, or a
single-active-job registry, `--workers >1` loads N copies of the model and breaks in-process
invariants (see `backend-architecture.md`). Scale the engine, not the worker count.

## Security — 0.0.0.0 is not localhost
Binding to all interfaces exposes the app to **everyone on the Wi-Fi**. Surface this loudly:

- **Secrets first**: if the app has auth, its signing key / admin password must be set to real
  values before exposing — repo defaults are often public.
- **The `Secure`-cookie foot-gun**: if the framework sets the session cookie `Secure`
  (HTTPS-only) in a "production" mode and you serve **plain HTTP** on the LAN, the browser
  silently **drops** the cookie → login appears to work but never sticks. Do NOT enable
  production/HTTPS-cookie mode for a plain-HTTP LAN host. Document it.
- **No auth?** Then say so plainly: the exposure is unauthenticated full access — that, not a
  cookie, is the risk. There's nothing to rotate, but also nothing gating access.
- **Don't add HTTPS/PWA unless asked**: a LAN cert means trusting a local CA on every device
  (or owning a domain). Plain HTTP is fine for a trusted LAN — but note an installable PWA /
  service worker needs a secure context and won't work over plain HTTP.

## Verify by observation (not a dry run)
- `lsof -iTCP:<port> -sTCP:LISTEN` shows `*:<port>` / `0.0.0.0`, **not** `127.0.0.1`.
- `curl` the machine's LAN IP **and** `http://<name>.local:<port>` → 2xx (build the frontend
  first, or `/` 404s).
- Occupy the base port, run again, confirm it serves on the next port.
- Tear down; confirm no leftover listeners. `git status`: confirm the package manager didn't
  rewrite `pyproject`/lockfiles (use `uv run --frozen`).
