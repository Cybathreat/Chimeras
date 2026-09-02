# Chimeras v3.0 — Kali Sandbox Image
# Council Session 19 consensus — 56 unique tools, efficiency-optimized
# Every tool earns its place. No duplicates. No redundancy.
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive

# ============================================================
# APT PACKAGES — single layer, cache cleaned after
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    \
    # ARIA (passive_recon)
    dnsutils \
    whois \
    curl \
    whatweb \
    \
    # LISA (active_scan)
    nmap \
    masscan \
    gobuster \
    sslscan \
    wpscan \
    \
    # BLOODHOUND (vuln_detection)
    exploitdb \
    \
    # WASP (web_exploit)
    sqlmap \
    commix \
    \
    # MARKSMAN (marksman)
    metasploit-framework \
    ncat \
    netcat-traditional \
    python3 \
    python3-pip \
    gcc \
    hydra \
    john \
    responder \
    samba \
    smbclient \
    socat \
    \
    # MAGICIAN (privesc)
    findutils \
    coreutils \
    openssh-client \
    \
    # THIEF (exfiltration)
    wget \
    tar \
    rsync \
    default-mysql-client \
    sqlite3 \
    \
    # SHARED UTILITIES
    jq \
    git \
    bash \
    gdb \
    strace \
    binutils \
    file \
    xxd \
    unzip \
    gzip \
    seclists \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# PIP PACKAGES — Python tools
# ============================================================
RUN pip3 install --break-system-packages \
    wafw00f \
    ssh-audit \
    wfuzz \
    arjun \
    impacket \
    certipy \
    bloodhound \
    || true

# ============================================================
# GO BINARIES — projectdiscovery + others (static, small)
# ============================================================
# Install Go for building tools
RUN apt-get update && apt-get install -y --no-install-recommends golang-go && rm -rf /var/lib/apt/lists/*

# Build Go tools from source (static binaries, minimal size)
RUN go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest && \
    go install github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest && \
    go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install github.com/lc/gau/v2/cmd/gau@latest && \
    go install github.com/ffuf/ffuf/v2@latest && \
    go install github.com/hahwul/dalfox/v2@latest && \
    go install github.com/PennyJacobs/enum4linux-ng@latest || true

# Copy Go binaries to /usr/local/bin
RUN cp /root/go/bin/* /usr/local/bin/ 2>/dev/null || true

# Download nuclei templates
RUN nuclei -update-templates 2>/dev/null || true

# ============================================================
# GITHUB BINARIES — not in apt or Go
# ============================================================
# testssl.sh
RUN git clone --depth 1 https://github.com/drwetter/testssl.sh.git /opt/testssl.sh && \
    ln -s /opt/testssl.sh/testssl.sh /usr/local/bin/testssl.sh || true

# linpeas + winpeas
RUN curl -sL https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh -o /usr/local/bin/linpeas && chmod +x /usr/local/bin/linpeas || true
RUN curl -sL https://github.com/carlospolop/PEASS-ng/releases/latest/download/winpeas.bat -o /usr/local/bin/winpeas.bat || true

# pspy (process monitoring without root)
RUN curl -sL https://github.com/dominicbreuker/pspy/releases/latest/download/pspy64 -o /usr/local/bin/pspy && chmod +x /usr/local/bin/pspy || true

# linux-exploit-suggester
RUN curl -sL https://raw.githubusercontent.com/mzet-/linux-exploit-suggester/master/les.sh -o /usr/local/bin/les && chmod +x /usr/local/bin/les || true

# mimikatz (Windows tool — stored for upload to Windows targets)
RUN mkdir -p /opt/tools/mimikatz && \
    curl -sL https://github.com/gentilkiwi/mimikatz/releases/latest/download/mimikatz_trunk.zip -o /opt/tools/mimikatz/mimikatz.zip && \
    cd /opt/tools/mimikatz && unzip -o mimikatz.zip 2>/dev/null && rm -f mimikatz.zip || true

# evil-winrm (Ruby gem)
RUN apt-get update && apt-get install -y --no-install-recommends ruby ruby-dev && \
    gem install evil-winrm && \
    apt-get remove -y ruby-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* || true

# enum4linux-ng (Python)
RUN pip3 install --break-system-packages enum4linux-ng || true

# netexec (pip)
RUN pip3 install --break-system-packages netexec || true

# ============================================================
# CLEANUP — remove Go cache, build deps, reduce image size
# ============================================================
RUN rm -rf /root/go /root/.cache /tmp/* /var/tmp/* && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create working directories
RUN mkdir -p /workspace /engagement

WORKDIR /workspace

CMD ["sleep", "infinity"]