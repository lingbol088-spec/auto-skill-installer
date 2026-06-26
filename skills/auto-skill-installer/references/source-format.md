# Source Format

Registry sources are loaded from two places:

1. The bundled default file at `assets/registry-sources.json`
2. The user override file at `$CODEX_HOME/auto-skill-installer/sources.json` for Codex-compatible setups

Each source object supports:

- `name`: Stable label used in output
- `repo`: GitHub repo in `owner/repo` format
- `path`: Directory inside the repo that contains one or more skills
- `ref`: Branch, tag, or commit-ish to read
- `tags`: Optional list of labels that help scoring and debugging

Example:

```json
{
  "name": "company-registry",
  "repo": "acme/agent-skills",
  "path": "skills",
  "ref": "main",
  "tags": ["internal", "approved"]
}
```

The installer merges user sources after bundled sources and deduplicates by `name + repo + path + ref`.
