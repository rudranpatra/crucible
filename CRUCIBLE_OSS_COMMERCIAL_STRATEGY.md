# Crucible — Open Source + Commercial Product Strategy

**Status:** Implementation specification  
**Audience:** Claude Code / engineering team  
**License baseline:** Apache License 2.0  
**Package:** `crucible-gym`

---

## 1. Objective

Crucible is an open-source adversarial testing engine for CI/CD pipelines.

The core product philosophy is:

> **Don't just scan the pipeline. Attack it.**

Crucible should test whether CI/CD security assumptions survive realistic adversarial behavior and produce evidence that can be inspected and replayed.

The product should have two clearly separated layers:

1. **Crucible OSS** — the open-source attack engine and developer-facing tooling.
2. **Crucible Commercial** — enterprise infrastructure, intelligence, management, scale, and assurance built around the OSS engine.

The commercial product must not make the OSS project intentionally useless. OSS is the distribution and trust engine.

---

# 2. Strategic Model

```text
                         CRUCIBLE
                            |
              +-------------+-------------+
              |                           |
        CRUCIBLE OSS              CRUCIBLE COMMERCIAL
        Apache 2.0                Proprietary services
              |                           |
        Attack Engine               Enterprise Control
        Attack Scenarios            Central Management
        CLI                         Historical Results
        Evidence                    Policy
        Replay                      RBAC / SSO
        SARIF                       Compliance Evidence
        CI Integration              Fleet / Org Scale
        Local Execution             Advanced Intelligence
              |                           |
              +-------------+-------------+
                            |
                     CRUCIBLE CORPUS
                            |
                 Continuous Security Research
```

---

# 3. Product Principles

## 3.1 OSS first

The OSS project must provide genuine value on its own.

Users should be able to:

```bash
pip install crucible-gym
```

and run meaningful adversarial CI/CD tests without purchasing anything.

## 3.2 Attack, don't only inspect

Crucible is not primarily a configuration scanner.

The core workflow is:

```text
Target
  ↓
Attack
  ↓
Execution
  ↓
Observation
  ↓
Evidence
  ↓
Result
  ↓
Replay
```

## 3.3 Evidence over explanation

Results should prioritize:

- What was attempted
- What executed
- What changed
- What was observed
- What evidence was collected
- Why the behavior matters
- How to reproduce it

Avoid making AI-generated explanations the core value proposition.

## 3.4 Reproducibility

Every meaningful attack should have a stable identifier and enough metadata to reproduce the result.

Example:

```text
Attack ID: CRU-GHA-001
Target: GitHub Actions workflow
Preconditions: ...
Attack: ...
Observed behavior: ...
Evidence: ...
Impact: ...
Replay: ...
```

## 3.5 Vendor-neutral output

Results should be exportable into formats that existing security workflows understand, including SARIF where appropriate.

---

# 4. Crucible OSS

## 4.1 Purpose

Crucible OSS is the executable adversarial testing engine.

It should answer:

> **Can this CI/CD environment actually withstand the attack scenario?**

## 4.2 OSS components

### A. CLI

Primary interface:

```bash
crucible <command>
```

The exact command structure should follow the existing implementation where possible. Do not unnecessarily redesign working commands.

Expected capabilities include:

```text
crucible audit
crucible attack
crucible compare
```

Preserve existing functionality unless there is a strong engineering reason to change it.

### B. Attack Engine

Responsible for:

- Loading attack definitions
- Validating prerequisites
- Preparing the test
- Executing the attack
- Capturing observations
- Producing evidence
- Cleaning up
- Returning a deterministic result

### C. Attack Definitions

Each attack should be represented as structured, versioned data/code with:

- Stable attack ID
- Name
- Description
- Category
- Target
- Preconditions
- Execution logic
- Expected secure behavior
- Expected vulnerable behavior
- Evidence requirements
- Impact
- Remediation guidance
- Replay information
- Version

### D. Evidence Engine

Evidence should be first-class output.

Minimum evidence concepts:

```text
timestamp
target
attack_id
execution_id
environment
actions
observations
artifacts
exit status
logs
diffs where applicable
```

Do not rely exclusively on prose summaries.

### E. Replay

A successful or failed attack should be replayable whenever technically possible.

The result should contain enough information to reproduce the scenario without relying on hidden state.

### F. CI Integration

Provide a straightforward way to run Crucible from CI.

Examples:

```text
GitHub Actions
GitLab CI
Jenkins
Generic shell/CI execution
```

Do not build provider-specific enterprise management into the OSS engine.

### G. SARIF

Where findings map naturally to SARIF, provide SARIF export.

This allows results to flow into existing developer/security workflows.

---

# 5. OSS Attack Corpus

The attack corpus is one of Crucible's most important strategic assets.

Initial categories should include:

```text
GitHub Actions
- Workflow injection
- Untrusted input execution
- Secret exposure
- Permission abuse
- Pull request manipulation
- Runner abuse
- Artifact manipulation

Dependencies / Supply Chain
- Dependency confusion
- Malicious dependency behavior
- Transitive dependency abuse
- Package substitution
- Maintainer compromise scenarios

Credentials
- Secret exposure
- Token misuse
- Credential exfiltration
- Excessive permissions

Build / Release
- Artifact tampering
- Release manipulation
- Signing/control bypass
- Deployment manipulation
```

Do not invent attacks simply to increase the count.

Every attack should have a clear security hypothesis and observable success/failure condition.

---

# 6. OSS Result Model

Define a stable result schema.

Conceptually:

```json
{
  "schema_version": "1.0",
  "attack_id": "CRU-GHA-001",
  "execution_id": "...",
  "target": "...",
  "started_at": "...",
  "completed_at": "...",
  "status": "passed|failed|blocked|error",
  "preconditions": [],
  "actions": [],
  "observations": [],
  "evidence": [],
  "impact": {},
  "remediation": {},
  "replay": {},
  "environment": {}
}
```

Use the existing implementation if a result schema already exists. Extend it rather than replacing it without need.

---

# 7. OSS Repository Structure

Use the existing repository structure as the source of truth.

Do not perform a large repository restructure merely to match this document.

Conceptually, the project should separate:

```text
crucible/
├── engine/
├── attacks/
├── evidence/
├── replay/
├── cli/
├── integrations/
├── schemas/
├── tests/
└── docs/
```

The actual names should follow the current codebase.

---

# 8. Commercial Crucible

Commercial Crucible should NOT simply be "Crucible OSS with more attack count."

It should solve enterprise-scale operational problems.

## 8.1 Commercial value proposition

> **Run adversarial CI/CD testing continuously across your organization and turn the results into persistent security evidence.**

Commercial capabilities should include:

### Centralized Management

- Multiple repositories
- Multiple organizations/projects
- Central result storage
- Search
- Filtering
- Ownership

### Historical Results

Track:

```text
Attack
  ↓
Previous result
  ↓
Current result
  ↓
Regression / improvement
```

This enables questions such as:

- Did this control improve?
- Did a previously blocked attack become successful?
- Which repositories are regressing?
- Which attack classes remain unresolved?

### Scheduling

Allow organizations to schedule adversarial tests:

```text
Daily
Weekly
Per release
On workflow change
On repository change
On demand
```

### Policy

Organizations should be able to define policies such as:

```text
CRU-GHA-001 must PASS
Critical attacks must not succeed
New failures require review
Production repositories must run weekly
```

### RBAC

Enterprise access controls should include roles such as:

```text
Admin
Security Engineer
Developer
Viewer
Auditor
```

### SSO

Commercial tier may provide:

- SAML
- OIDC
- Enterprise identity integration

### Enterprise Evidence

Provide persistent evidence packages suitable for:

- Security reviews
- Internal audits
- Customer assurance
- Compliance workflows
- Incident investigation

### Reporting

Reports should show:

- Attack coverage
- Successful attacks
- Failed attacks
- Regressions
- Repository risk
- Trends
- Remediation status

Avoid building a dashboard merely for visual appeal. Every commercial UI must answer an operational security question.

---

# 9. Commercial Attack Intelligence

The OSS corpus should remain useful.

Commercial value can come from continuously maintained intelligence:

```text
New attack research
       ↓
Validation
       ↓
Crucible attack
       ↓
OSS-compatible where appropriate
       ↓
Enterprise intelligence / orchestration
```

Potential commercial assets:

- Advanced attack packs
- Early research releases
- Campaign-specific scenarios
- Enterprise attack policies
- Cross-repository correlation
- Attack trend intelligence
- Managed attack updates

Do not artificially remove basic security functionality from OSS just to force upgrades.

---

# 10. Open Source vs Commercial Boundary

## Keep in OSS

```text
Core attack execution
Basic attack definitions
CLI
Local execution
Evidence generation
Replay
Basic CI integrations
SARIF
Basic result schema
Community contribution framework
```

## Commercial

```text
Centralized platform
Organization management
RBAC
SSO
Scheduling at scale
Historical analytics
Policy management
Enterprise evidence
Fleet management
Advanced correlation
Managed intelligence
Enterprise support
SLA
```

The boundary may evolve. Do not hard-code commercial dependencies into the OSS engine.

---

# 11. Architecture Boundary

The OSS engine must remain independently usable.

Preferred architecture:

```text
                 +----------------------+
                 |   Crucible CLI       |
                 +----------+-----------+
                            |
                 +----------v-----------+
                 |   OSS Attack Engine  |
                 +----------+-----------+
                            |
          +-----------------+-----------------+
          |                 |                 |
      Attacks           Evidence          Replay
          |                 |                 |
          +-----------------+-----------------+
                            |
                     Result Schema
                            |
              +-------------+-------------+
              |                           |
         Local Output              Commercial Adapter
                                          |
                                  +-------v-------+
                                  | Commercial    |
                                  | Platform      |
                                  +---------------+
```

The OSS engine must not require the commercial service.

---

# 12. Commercial Adapter

If needed, introduce a clean adapter/interface rather than embedding commercial API calls throughout the OSS code.

Conceptually:

```python
class ResultSink:
    def publish(self, result):
        raise NotImplementedError
```

OSS implementations:

```text
LocalFileSink
StdoutSink
SARIFSink
```

Commercial implementation:

```text
CrucibleCloudSink
```

Do not add proprietary code to the OSS repository unless there is a clear licensing and architectural reason.

---

# 13. Brand and Trademark

Apache 2.0 permits broad use, modification, distribution, and sale of the software. The license itself does not grant trademark rights. The current license explicitly reserves the licensor's trade names, trademarks, service marks, and product names. 

Therefore:

- Keep **Crucible** as the official product/project identity.
- Keep official GitHub, PyPI, documentation, and website channels clearly identified.
- Add a trademark/branding policy.
- Do not imply that third-party forks are official Crucible releases.
- Use an official naming convention for verified attacks and releases.

Trademark protection should be handled separately from the software license with appropriate legal advice.

---

# 14. Apache 2.0 Compliance

The current project is licensed under Apache 2.0.

Apache 2.0 grants users broad rights to reproduce, modify, distribute, sublicense, and sell the Work. 

Therefore, the project must be designed with the assumption that:

> **A third party may commercially use or fork the OSS code.**

Do not build the business plan around preventing this.

The defense is differentiation:

```text
OSS Code
    +
Attack Corpus
    +
Security Research
    +
Community
    +
Brand
    +
Enterprise Platform
    +
Distribution
    =
Crucible Business
```

---

# 15. Contributor and IP Controls

Before accepting significant external contributions:

1. Define contribution guidelines.
2. Define how copyright is handled.
3. Add a Developer Certificate of Origin or CLA only if legally and strategically justified.
4. Ensure third-party dependencies have compatible licenses.
5. Maintain attribution and NOTICE requirements.
6. Document how commercial and OSS code are separated.

Do not change contributor licensing requirements casually after the project has accumulated contributors.

---

# 16. Security Requirements

Crucible itself is security tooling and can execute real actions.

Therefore:

- Clearly document attack scope.
- Require explicit target selection.
- Avoid destructive defaults.
- Provide safe/dry-run behavior where appropriate.
- Clearly distinguish test environments from production.
- Capture execution boundaries.
- Never silently exfiltrate secrets or telemetry.
- Never send execution data to a commercial service without explicit configuration.
- Document required permissions.

---

# 17. Product Telemetry

OSS should be privacy-respecting by default.

Preferred:

```text
No mandatory telemetry
No mandatory account
No mandatory cloud service
No mandatory API key
```

Commercial telemetry/centralization should be explicit and configurable.

---

# 18. Testing Requirements

Every attack must have tests for:

### Positive / Secure Case

The security control works.

Expected:

```text
Attack blocked
Evidence captured
Result = PASS
```

### Negative / Vulnerable Case

The security control fails.

Expected:

```text
Attack succeeds
Evidence captured
Result = FAIL
```

### Error Case

The environment is invalid or the attack cannot execute.

Expected:

```text
Result = ERROR
```

### Blocked Case

A prerequisite prevents execution.

Expected:

```text
Result = BLOCKED
```

Do not treat ERROR or BLOCKED as PASS.

---

# 19. Quality Gate for New Attacks

No attack should be merged unless it has:

- Unique attack ID
- Security hypothesis
- Preconditions
- Execution logic
- Secure expected behavior
- Vulnerable expected behavior
- Evidence definition
- Cleanup behavior
- Tests
- Documentation
- Replay information where feasible

The attack must demonstrate an actual security property.

Avoid "demo attacks" that only produce impressive-looking output.

---

# 20. Documentation Strategy

The public documentation should answer:

1. What is Crucible?
2. Why adversarial CI/CD testing?
3. Installation
4. Quick start
5. First attack
6. Understanding evidence
7. Replay
8. CI integration
9. Writing attacks
10. Attack catalog
11. Architecture
12. Security model
13. Contributing
14. License

Commercial documentation should be separate:

```text
docs/
├── oss/
└── commercial/
```

Do not advertise commercial features as required dependencies for the OSS workflow.

---

# 21. Recommended README Positioning

Primary statement:

> **Crucible is an open-source adversarial testing engine for CI/CD pipelines.**

Supporting statement:

> **Don't just scan your pipeline. Attack it.**

Core workflow:

```text
Attack → Execute → Observe → Prove → Replay
```

Avoid positioning Crucible primarily as:

- An AI security tool
- A dashboard
- A configuration scanner
- A generic vulnerability scanner

The differentiation is **behavioral/adversarial validation with evidence**.

---

# 22. Recommended Growth Loop

```text
Developer discovers Crucible
          ↓
pip install crucible-gym
          ↓
Runs first attack
          ↓
Gets evidence
          ↓
Adds Crucible to CI
          ↓
Shares result
          ↓
Community contributes attack
          ↓
Attack corpus grows
          ↓
Crucible becomes more useful
          ↓
Organizations need centralized control
          ↓
Commercial adoption
```

The OSS project is therefore a distribution mechanism, not merely a free edition.

---

# 23. Implementation Roadmap

## Phase 1 — Stabilize OSS

- [ ] Verify Apache 2.0 licensing and notices
- [ ] Verify package metadata
- [ ] Verify `pip install crucible-gym`
- [ ] Stabilize CLI
- [ ] Stabilize attack/result schema
- [ ] Stabilize evidence format
- [ ] Stabilize replay
- [ ] Add CI integration
- [ ] Improve README
- [ ] Add attack contribution guide

## Phase 2 — Build Attack Corpus

- [ ] Define attack ID convention
- [ ] Define attack schema
- [ ] Create initial attack categories
- [ ] Add secure/vulnerable fixtures
- [ ] Add deterministic tests
- [ ] Publish attack documentation
- [ ] Establish security research workflow

## Phase 3 — Community

- [ ] Contribution guide
- [ ] Issue templates
- [ ] Attack request process
- [ ] Security policy
- [ ] Release process
- [ ] Changelog
- [ ] Community examples

## Phase 4 — Commercial Foundation

- [ ] Define result ingestion API
- [ ] Define authentication model
- [ ] Define tenant model
- [ ] Define repository model
- [ ] Define centralized result storage
- [ ] Define scheduling
- [ ] Define policy engine
- [ ] Define RBAC
- [ ] Define enterprise evidence

## Phase 5 — Commercial Product

- [ ] Central result platform
- [ ] Organization/repository management
- [ ] Scheduling
- [ ] Policy
- [ ] Historical comparison
- [ ] Enterprise reporting
- [ ] SSO/RBAC
- [ ] Enterprise evidence
- [ ] Advanced intelligence
- [ ] Support/SLA

---

# 24. Claude Code Implementation Rules

When implementing this specification:

### Rule 1

**Inspect the existing repository before changing architecture.**

Do not rewrite working components merely to match this document.

### Rule 2

**Preserve existing CLI behavior unless explicitly changing it.**

Existing users must not be broken unnecessarily.

### Rule 3

**Do not introduce commercial dependencies into the OSS runtime.**

The OSS CLI must work offline/local where the existing design permits.

### Rule 4

**Use interfaces for future commercial integration.**

Do not hard-code a cloud service into the attack engine.

### Rule 5

**Prefer additive changes.**

Extend existing schemas and APIs where possible.

### Rule 6

**Every attack needs deterministic tests.**

Do not accept an attack because it produces interesting output.

### Rule 7

**Security boundaries must be explicit.**

Clearly identify:

- attack execution
- target
- permissions
- evidence
- cleanup

### Rule 8

**Do not collect telemetry by default.**

### Rule 9

**Do not add AI merely for positioning.**

AI can be added later where it creates measurable value. It is not the core Crucible proposition.

### Rule 10

**Commercial functionality must be architecturally separable.**

A user installing:

```bash
pip install crucible-gym
```

must receive a complete, useful OSS product.

---

# 25. Definition of Done

Crucible OSS is considered production-ready when:

- [ ] Installation works from PyPI
- [ ] A new user can run the first attack quickly
- [ ] Attack IDs are stable
- [ ] Results are deterministic where expected
- [ ] Evidence is persisted
- [ ] Results are replayable where feasible
- [ ] CI integration works
- [ ] SARIF export works where applicable
- [ ] Secure and vulnerable test fixtures exist
- [ ] Documentation is complete
- [ ] License and attribution are correct
- [ ] Security policy exists
- [ ] Contribution process exists

Commercial Crucible is ready for initial enterprise pilots when:

- [ ] Results can be centrally collected
- [ ] Organizations/repositories can be managed
- [ ] Authentication and RBAC work
- [ ] Historical results work
- [ ] Scheduling works
- [ ] Policies can be defined
- [ ] Evidence can be exported
- [ ] OSS remains independently usable
- [ ] Tenant isolation is tested
- [ ] Security logging/auditability is implemented

---

# 26. Final Product Position

Crucible should not compete on:

> "We have another security scanner."

It should compete on:

> **"We continuously try to break your CI/CD security assumptions and give you evidence of what actually happened."**

The open-source engine creates trust and distribution.

The attack corpus creates security intelligence.

The commercial platform creates operational scale.

The brand creates identity.

The community creates compounding value.

That is the intended Crucible business model.
