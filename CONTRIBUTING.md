# Contributing to Crucible

**Maintainer:** [rudranpatra](https://github.com/rudranpatra)

Thank you for your interest. Crucible is an adversarial CI/CD testing engine and contributions are welcome.

## Ground rules

- One concern per PR. Bug fixes and feature additions should be separate.
- All tests must pass before review (`pytest crucible/tests/ -v`).
- Lint must be clean (`ruff check crucible/`).
- Type check must pass (`mypy crucible/ --ignore-missing-imports --exclude tests/`).
- No external dependencies added without discussion in an issue first.

## Development setup

```bash
git clone https://github.com/rudranpatra/crucible.git
cd crucible
pip install -e ".[dev,web]"
```

Run tests:

```bash
cd crucible
pytest tests/ -v --tb=short
```

Run lint:

```bash
ruff check crucible/
```

Run the demo:

```bash
cd crucible
crucible attack --demo
```

## Submitting changes

1. Open an issue describing the problem or feature before writing code for anything non-trivial.
2. Fork the repo and create a branch from `main`.
3. Make your changes. Add or update tests covering the change.
4. Run the full test suite and lint — both must pass.
5. Open a pull request. The `crucible-self-check` CI job will run automatically and post a resilience score.

## Adding a new attack type

1. Add a class in `crucible/attacks/strategies.py` inheriting `BaseAdversarialAgent`.
2. Implement `generate_mutations()` and `apply_mutation()`.
3. Register it in `ATTACK_REGISTRY` in `crucible/runner.py`.
4. Add tests in `crucible/tests/test_crucible.py`.
5. Update `CHANGELOG.md` under `[Unreleased]`.

## Reporting bugs

Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) template. Include the trace ID if you have one — it makes reproduction much faster.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to abide by its terms.
