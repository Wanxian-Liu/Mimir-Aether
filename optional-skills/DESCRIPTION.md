# Optional Skills

Official skills maintained by Nous Research that are **not activated by default**.

These skills live in this repository under `optional-skills/` and are not copied into the default agent runtime tree during setup. They are discoverable via the Skills Hub:

```bash
hermes skills browse               # browse all skills, official shown first
hermes skills browse --source official  # browse only official optional skills
hermes skills search <query>       # finds optional skills labeled "official"
hermes skills install <identifier> # copies into the agent skills directory (under $MIMIR_AETHER_HOME; default ~/.mimiraether) and activates
```

## Why optional?

Some skills are useful but not broadly needed by every user:

- **Niche integrations** — specific paid services, specialized tools
- **Experimental features** — promising but not yet proven
- **Heavyweight dependencies** — require significant setup (API keys, installs)

By keeping them optional, we keep the default skill set lean while still
providing curated, tested, official skills for users who want them.
