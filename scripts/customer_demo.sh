#!/usr/bin/env bash
# Standalone Crucible demo: local engine only (no signup, no network, no Cloud). Creates throwaway workflow files in a temp
# directory, runs `crucible audit`, and asserts the documented behavior. Exits nonzero on any unexpected result.
#   pip install crucible-gym   (or: pip install .)   then   bash scripts/customer_demo.sh
set -uo pipefail
command -v crucible >/dev/null || { echo "crucible not on PATH (pip install crucible-gym)" >&2; exit 2; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fail=0
check() { if [ "$2" = "ok" ]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi; }

cat > "$T/unpinned.yml" <<'YML'
name: ci
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
      - run: echo hello
YML
cat > "$T/pinned.yml" <<'YML'
name: ci
on: push
permissions: { contents: read }
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@8e5e7e5ab8b370d6c329ec480221332ada57f0ab
      - run: echo hello
YML
printf 'name: [unclosed\n' > "$T/broken.yml"

out="$(crucible audit "$T/unpinned.yml" 2>&1)"; rc=$?
{ [ $rc -eq 0 ] && grep -q "not a pinned commit SHA" <<<"$out"; } && check "unpinned action is reported" ok || check "unpinned action is reported (rc=$rc)" bad
grep -q "Resilience: 85/100" <<<"$out" && check "score for one finding is 85/100 (15-point deduction)" ok || check "score for one finding is 85/100" bad
out="$(crucible audit "$T/pinned.yml" 2>&1)"; rc=$?
{ [ $rc -eq 0 ] && grep -q "No findings" <<<"$out" && grep -q "100/100" <<<"$out"; } && check "SHA-pinned workflow has no findings (100/100)" ok || check "SHA-pinned workflow has no findings (rc=$rc)" bad
crucible audit "$T/broken.yml" >/dev/null 2>&1; [ $? -ne 0 ] && check "malformed YAML fails with a nonzero exit" ok || check "malformed YAML fails with a nonzero exit" bad
crucible audit "$T/missing.yml" >/dev/null 2>&1; [ $? -ne 0 ] && check "missing file fails with a nonzero exit" ok || check "missing file fails with a nonzero exit" bad
echo "Scope: local mode runs one check (unpinned GitHub Actions). It does not detect pull_request_target abuse, script injection or secret exposure; local mode does not cover them."
exit $fail
