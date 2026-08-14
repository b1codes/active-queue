Keep this project's coding-agent tooling current: refresh Claude Code, Antigravity, and Codex CLI plugin marketplaces and installed plugins (whichever of those CLIs are on PATH), then check for skill updates.

Run:

    b1 update-project

Pass `--claude`, `--agy`, or `--codex` to target a single CLI instead of auto-detecting, `--all` to force all three, or `--skip-skills` to skip the `npx skills update` step. After it runs, summarize what got updated (or skipped, and why).
