# Vendored Claude Code plugin: `watch`

The [`claude-watch`](https://github.com/taoufik123-collab/claude-watch) plugin is
vendored into this repo's `.claude/` directory instead of installed via
`/plugin` (which isn't available in the Claude Code on the web environment).
Vendoring it here means the skill travels with the repo and works in every
session without a per-machine install step.

## What's installed

| Path | Purpose |
|------|---------|
| `skills/watch/SKILL.md` | The `watch` skill definition (invocable via `/watch`). |
| `skills/watch/scripts/` | Bundled Python pipeline (download, frames, transcribe, report, setup). |
| `commands/watch.md` | The `/watch` slash command that invokes the skill. |
| `hooks/scripts/check-setup.sh` | SessionStart status check (silent when ready). |
| `settings.json` | Wires the SessionStart hook. |

## Runtime dependencies

The skill itself is installed and ready. To actually process videos it needs a
one-time system setup (not committed here, as they're machine-level tools):

```bash
python3 .claude/skills/watch/scripts/setup.py
```

This installs `ffmpeg` + `yt-dlp` and scaffolds `~/.config/watch/.env`. Add a
`GROQ_API_KEY` (preferred) or `OPENAI_API_KEY` there to unlock the Whisper
transcription fallback; videos with native captions work without a key.

Usage: `/watch <video-url-or-path> [why you're watching it]`

Upstream: https://github.com/taoufik123-collab/claude-watch
