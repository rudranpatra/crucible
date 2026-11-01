# Crucible

> A local, offline static check for mutable third-party GitHub Actions references.

`crucible-gym` 0.5.4's local mode audits workflow YAML for Actions referenced by mutable tags or branches. It does not execute workflow commands or contact the network. Crucible Cloud is a separate private, self-hosted pilot, not a public hosted service or a generally available six-agent engine. Its recommended pilot path is local execution with explicit result-summary upload.

See [crucible/README.md](crucible/README.md) for package details and the OSS/Cloud split. For the verified local customer demo, see [CUSTOMER_DEMO.md](CUSTOMER_DEMO.md).

- PyPI: https://pypi.org/project/crucible-gym/
- License: [Apache 2.0](LICENSE)
