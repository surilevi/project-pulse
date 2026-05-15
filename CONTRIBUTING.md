# Contributing

Thanks for helping improve `Project Pulse`. The project is small, local-first, and privacy-sensitive, so changes should stay easy to review and conservative around filesystem data.

## Development Setup

```powershell
pip install -e .[dev]
git config core.hooksPath .githooks
```

## Quality Checks

Run the full local check set before opening a pull request:

```powershell
python -m ruff check src tests
python -m pytest
python -m project_pulse safety-audit
```

## Pull Request Guidelines

1. Keep changes focused and reviewable.
2. Update documentation when behavior or commands change.
3. Add tests for scanner, publisher, session, or audit edge cases.
4. Explain privacy, security, or workflow tradeoffs when a change touches local paths, persistence, publishing, or process detection.
5. Avoid committing generated output, local state, machine-specific config, or screenshots that reveal private paths.

## Design Principles

- Default to local-only behavior.
- Prefer explicit commands over background automation.
- Keep reports relative-path friendly unless the user opts into absolute paths.
- Treat publishing as a review step, not an automatic side effect.
- Make scoring and decisions explainable from named inputs.
