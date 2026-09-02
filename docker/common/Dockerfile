# Chimeras v3.0 — Common base for all tiers
# Shared setup: user, workspace, entrypoint hook
#
# Scope enforcement is HOST-SIDE via nsenter (host injects nftables rules
# into container netns). Container itself runs WITHOUT NET_ADMIN — a
# compromised bot cannot flush its own firewall. nft binary is present only
# as an in-namespace fallback if host-side injection is unavailable.

ARG BASE_IMAGE=kalilinux/kali-rolling:latest
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

# nft binary (no NET_ADMIN cap needed to LIST rules; host does the enforcing)
RUN apt-get update && apt-get install -y --no-install-recommends nftables && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/chimeras-entrypoint.sh
RUN chmod +x /usr/local/bin/chimeras-entrypoint.sh

RUN useradd -m -s /bin/bash pentester && \
    echo "pentester ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /workspace /engagement /evidence
WORKDIR /workspace

# Entry: default keep-alive; executor runs tools via docker exec
CMD ["sleep", "infinity"]