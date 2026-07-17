# Configuration

## swarm-config.json

Each mission has its own `swarm-config.json` that configures the LLM provider for each bot.

```json
{
  "version": "1.0",
  "created": "2026-07-16T23:05:28",
  "mission_name": "My Pentest",
  "bots": {
    "warchief":   {"provider": "openai", "model": "gpt-4o"},
    "aria":        {"provider": "openai", "model": "gpt-4o"},
    "lisa":        {"provider": "openai", "model": "gpt-4o"},
    "bloodhound":  {"provider": "openai", "model": "gpt-4o"},
    "surgeon":     {"provider": "openai", "model": "gpt-4o"},
    "pathologist": {"provider": "openai", "model": "gpt-4o"},
    "magician":    {"provider": "openai", "model": "gpt-4o"},
    "thief":       {"provider": "openai", "model": "gpt-4o"},
    "bookkeeper":  {"provider": "openai", "model": "gpt-4o"}
  }
}
```

## Per-Bot Configuration

Each bot can use a different provider and model. Mix and match:

```json
{
  "bots": {
    "warchief":   {"provider": "anthropic", "model": "claude-opus-4-6"},
    "aria":        {"provider": "ollama", "model": "qwen2.5:14b"},
    "lisa":        {"provider": "google", "model": "gemini-2.5-flash"},
    "bloodhound":  {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    "surgeon":     {"provider": "anthropic", "model": "claude-opus-4-6"},
    "pathologist": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    "magician":    {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    "thief":       {"provider": "ollama", "model": "qwen2.5:14b"},
    "bookkeeper":  {"provider": "ollama", "model": "qwen2.5:7b"}
  }
}
```

## Custom Gateways (base_url)

Any OpenAI-compatible endpoint works via `base_url`:

### Ollama Cloud
```json
{
  "bots": {
    "warchief": {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"}
  }
}
```
API key: `OLLAMA_API_KEY`

### vLLM / LM Studio
```json
{
  "bots": {
    "warchief": {"provider": "openai", "model": "meta-llama/Llama-3.3-70B-Instruct", "base_url": "http://localhost:8000/v1"}
  }
}
```

### Azure OpenAI
```json
{
  "bots": {
    "warchief": {"provider": "openai", "model": "gpt-4o", "base_url": "https://your-resource.openai.azure.com/openai/deployments/gpt-4o"}
  }
}
```

## Environment Variables

| Variable | Provider | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | openai | OpenAI API key |
| `OLLAMA_API_KEY` | openai | Ollama Cloud API key (OpenAI-compatible) |
| `ANTHROPIC_API_KEY` | anthropic | Anthropic API key |
| `GOOGLE_API_KEY` | google | Google AI API key |
| `GROQ_API_KEY` | groq | Groq API key |
| `OPENROUTER_API_KEY` | openrouter | OpenRouter API key |
| `OPENAI_BASE_URL` | openai | Default base_url for all OpenAI bots |
| `ANTHROPIC_BASE_URL` | anthropic | Default base_url for all Anthropic bots |

Config `base_url` takes precedence over environment `base_url`.

## Interactive Setup

Run `python main.py` with no arguments for interactive setup. It prompts for:
- Mission name
- Objectives
- Scope (IPs, domains, CIDR ranges)
- Rules of engagement

Then creates the mission directory, engagement folder structure, and a default `swarm-config.json`.