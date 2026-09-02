# Chimeras v3.0 — Tier 2: Discovery Mid Image (Lisa, Bloodhound, Wasp)
# Scanning + vuln detection + web exploitation. No Metasploit (exploit tier only).
FROM kalilinux/kali-rolling:latest AS gobuilder

RUN apt-get update && apt-get install -y --no-install-recommends golang-go git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV GOBIN=/out/bin
RUN mkdir -p /out/bin && \
    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest && \
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest && \
    go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install -v github.com/lc/gau/v2/cmd/gau@latest && \
    go install -v github.com/ffuf/ffuf/v2@latest && \
    go install -v github.com/hahwul/dalfox/v2@latest

FROM kalilinux/kali-rolling:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    masscan \
    gobuster \
    sslscan \
    wpscan \
    sqlmap \
    commix \
    exploitdb \
    netexec \
    curl \
    whatweb \
    whois \
    dnsutils \
    iputils-ping \
    python3 \
    python3-pip \
    jq \
    git \
    bash \
    ncat \
    nftables \
    wfuzz \
    && rm -rf /var/lib/apt/lists/*

# One pip package per RUN — a failure never cascades, and is VISIBLE at build time
RUN pip3 install --break-system-packages wafw00f
RUN pip3 install --break-system-packages ssh-audit
RUN pip3 install --break-system-packages arjun

COPY --from=gobuilder /out/bin/ /usr/local/bin/

RUN nuclei -update-templates 2>/dev/null || true

# testssl.sh
RUN git clone --depth 1 https://github.com/drwetter/testssl.sh.git /opt/testssl.sh && \
    ln -s /opt/testssl.sh/testssl.sh /usr/local/bin/testssl.sh

COPY entrypoint.sh /usr/local/bin/chimeras-entrypoint.sh
RUN chmod +x /usr/local/bin/chimeras-entrypoint.sh

RUN useradd -m -s /bin/bash pentester && \
    echo "pentester ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /workspace /engagement /evidence
WORKDIR /workspace

CMD ["sleep", "infinity"]