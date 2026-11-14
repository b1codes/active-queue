from __future__ import annotations

# Cloud Run reserves URL paths ending in "z": a request for /healthz to a run.app URL gets
# a Google 404 and never reaches the container. External callers (the post-deploy smoke
# check, uptime monitors) use /health. /healthz stays for Cloud Run's own probes, which
# connect to the container directly, and for local tooling.
#
# The router serves exactly these paths and the rate limiter exempts exactly these, so a
# new health path added here can't end up IP-rate-limited (uptime probes would see 429s).
# Kept dependency-free so the middleware can import it without the router's Firestore.
HEALTH_PATHS = ("/health", "/healthz")
