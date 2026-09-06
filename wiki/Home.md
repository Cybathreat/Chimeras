# Chimeras Wiki

Welcome to the Chimeras **v3.2** wiki — documentation for the autonomous adaptive AI penetration testing swarm.

> The core architecture pages below describe the v2 adaptive graph, which remains the foundation. v3.0 added Docker sandboxing, SARIF export, web search, budget caps, Jinja2 templates, tests + CI. v3.1 added PDF/DOCX reports, Evidence Locker, Compliance Mapper, Retest Verifier, Context Compaction, Coverage Tracker. v3.2 added the client portal, proposal generator, retest diff, FR/AR locales, white-label branding, ticketing export, and SOC 2/NIS2/NCA ECC compliance. See [CHANGELOG.md](https://github.com/Cybathreat/Chimeras/blob/main/CHANGELOG.md) for details.

## Pages

- [Architecture](Architecture) — v2 adaptive graph design, WarChief decision router, reasoning loop, and state schema
- [Bot Reference](Bot-Reference) — All 9 bots, their roles, scopes, categories, and v2 features
- [Tool Scoping](Tool-Scoping) — 3-tier enforcement: category check, shell injection block, target validation
- [Configuration](Configuration) — LLM providers, custom gateways, v1→v2 auto-migration, and swarm-config.json
- [Getting Started](Getting-Started) — Installation, TUI wizard, setup, and first run
- [Report Format](Report-Format) — Professional pentest report with decision audit trail and cleanup status
- [Security & Legal](Security-and-Legal) — Two human gates, code-level scope enforcement, authorization requirements
