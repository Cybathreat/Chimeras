# Chimeras v3.0 — Tier 2: Discovery Mid Image (Lisa, Bloodhound, Wasp)
# ~400MB. Scanning + vuln detection + web exploitation. No exploit tools.
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
    nikto \
    exploitdb \
    curl \
    whatweb \
    whois \
    dnsutils \
    python3 \
    python3-pip \
    jq \
    git \
    bash \
    ncat \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages wafw00f ssh-audit wfuzz arjun || true

COPY --from=gobuilder /out/bin/ /usr/local/bin/

RUN nuclei -update-templates 2>/dev/null || true

# testssl.sh
RUN git clone --depth 1 https://github.com/drwetter/testssl.sh.git /opt/testssl.sh && \
    ln -s /opt/testssl.sh/testssl.sh /usr/local/bin/testssl.sh || true

RUN useradd -m -s /bin/bash pentester && \
    echo "pentester ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /workspace /engagement /evidence
WORKDIR /workspace

CMD ["sleep", "infinity"]