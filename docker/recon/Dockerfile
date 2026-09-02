# Chimeras v3.0 — Tier 1: Recon Slim Image (ARIA)
# ~200MB. DNS + passive recon only. Minimal attack surface.
FROM kalilinux/kali-rolling:latest AS gobuilder

RUN apt-get update && apt-get install -y --no-install-recommends golang-go git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV GOBIN=/out/bin
RUN mkdir -p /out/bin && \
    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest && \
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install -v github.com/lc/gau/v2/cmd/gau@latest

FROM kalilinux/kali-rolling:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsutils \
    whois \
    curl \
    whatweb \
    python3 \
    python3-pip \
    jq \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages wafw00f || true

COPY --from=gobuilder /out/bin/ /usr/local/bin/

RUN useradd -m -s /bin/bash pentester && \
    echo "pentester ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /workspace /engagement /evidence
WORKDIR /workspace

CMD ["sleep", "infinity"]