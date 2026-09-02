#!/bin/bash
# Chimeras v3.0 — Container Entrypoint
#
# Scope enforcement model (v3.0 hardened):
#   HOST-SIDE: TieredDockerExecutor injects nftables rules into this
#   container's network namespace via `nsenter` AFTER container start.
#   The container runs WITHOUT NET_ADMIN — a compromised bot CANNOT
#   modify or flush its own firewall. This is strictly stronger than
#   in-container enforcement (Strix has neither).
#   This script never runs nft itself by default.
#
# Env vars (set by executor):
#   CHIMERAS_BOT_NAME      — bot identity (aria, lisa, marksman, ...)
#   CHIMERAS_PHASE         — engagement phase
#   CHIMERAS_SCOPE_IPS     — comma-separated in-scope IP/CIDRs (for /etc/hosts + logging)
#   CHIMERAS_SCOPE_DOMAINS — comma-separated in-scope domains
#   CHIMERAS_EVIDENCE_DIR  — evidence log location (mounted volume)
#   CHIMERAS_TTL           — seconds until auto-kill (0 = disabled)

set -e

EVIDENCE_DIR="${CHIMERAS_EVIDENCE_DIR:-/evidence}"
BOT_NAME="${CHIMERAS_BOT_NAME:-unknown}"
PHASE="${CHIMERAS_PHASE:-unknown}"
SCOPE_IPS="${CHIMERAS_SCOPE_IPS:-}"
SCOPE_DOMAINS="${CHIMERAS_SCOPE_DOMAINS:-}"
TTL="${CHIMERAS_TTL:-0}"

mkdir -p "$EVIDENCE_DIR"

# ============================================================
# 1. SCOPE-AWARE DNS — resolve scoped domains to /etc/hosts
#    Out-of-scope lookups still fail at the host-side firewall.
# ============================================================
if [ -n "$SCOPE_DOMAINS" ]; then
    IFS=',' read -ra DOMAINS <<< "$SCOPE_DOMAINS"
    for domain in "${DOMAINS[@]}"; do
        domain=$(echo "$domain" | xargs)
        [ -z "$domain" ] && continue
        ip=$(getent hosts "$domain" 2>/dev/null | awk '{print $1}' | head -1)
        if [ -n "$ip" ] && ! grep -q " $domain\$" /etc/hosts 2>/dev/null; then
            echo "$ip $domain" >> /etc/hosts
        fi
    done
    echo "[entrypoint] Scope-aware DNS: ${#DOMAINS[@]} domains pinned"
fi

# ============================================================
# 2. EVIDENCE CHAIN INIT — hash chain seed for this container
# ============================================================
EVIDENCE_LOG="$EVIDENCE_DIR/evidence_${BOT_NAME}.jsonl"
if [ ! -f "$EVIDENCE_LOG" ]; then
    echo "{\"event\":\"container_init\",\"bot\":\"$BOT_NAME\",\"phase\":\"$PHASE\",\"scope_ips\":\"$SCOPE_IPS\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > "$EVIDENCE_LOG"
fi
echo "[entrypoint] Evidence chain: $EVIDENCE_LOG"

# ============================================================
# 3. TTL — auto-kill (prevents zombie containers)
# ============================================================
if [ "$TTL" -gt 0 ] 2>/dev/null; then
    (sleep "$TTL" && kill -TERM 1) &
    echo "[entrypoint] TTL: ${TTL}s"
fi

echo "[entrypoint] Bot=$BOT_NAME Phase=$PHASE — sandbox ready (host-side firewall pending injection)"

exec "$@"