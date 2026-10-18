# Release QA evidence

Branch: codex/release-qa. Baseline source commit is the parent of the QA commit, without concurrent final-sprint correction fixes. Local checks are macOS arm64, Python 3.11, Node 26.8.1. New CI specifies Ubuntu + Node 22; its remote execution is pending.

- Fresh `make test` with newly bootstrapped locked Python environment: PASS. Core 664, Pi 77, knowledge 265, assets 41, IKEA 82; web 29; G2 Vitest 208 across 15 files. Knowledge emits six existing PyMuPDF/Pillow deprecation warnings.
- Contracts: nine exported schemas, 22 Python examples and 22 TypeScript examples. Generic-boundary lint and repository secret-pattern scan PASS (867 reported entries, before removal of temporary dependency symlinks).
- `npm run build` and `npm run pack`: PASS. `g2/ghostbuild.ehpk`, 50,472 bytes, SHA256 8534bc3798dc4263be17e0b251b81702fccbf0b9e1a7fd480ba5c5a6885d9797. This portable package uses the checked-in localhost backend; a physical deployment needs `BACKEND=http://<laptop-ip>:8787 make g2-pack`.
- `uv sync --frozen --all-groups`: PASS in a new /tmp environment. CI workflow passes actionlint 1.7.12.
- Official installed simulator 0.9.5 against actual core: PASS 15 checkpoints, two generic playbooks, all three images with SDK success, grounded contextual answer, manual HUMAN CONFIRMED completion, final quiet frame. RGBA screenshot confirms zero lit pixels on final quiet frame. These are simulated gestures, not physical task completion or physical G2 verification.
- Real Chromium phone companion: desktop 1440x1000 and mobile 390x844. No horizontal overflow on mobile. Ready-guide selection and Mac diagnostic choice work; task transitions preserve the correct guide caption after the fix. Backend disconnect shows CORE UNREACHABLE; restart resumes the same diagnostic question and clears the warning.
- Browser exposed missing compiled Mac assets in a fresh checkout, producing two HTTP 404s with honest text fallback. Integrator notified; another agent owns the prepared-asset fix. This must be rechecked on the final combined branch.
- No paid provider calls, live voice tests, physical glasses tests, or physical Pi tests were performed in this lane. Simulator needed one relaunch after becoming stale during repeated mixed browser/simulator experiments; the final run completed from clean simulator launch.

## Security disposition

`pip-audit` against all pinned dependencies exported from uv.lock: no known vulnerabilities. `npm audit --omit=dev`: zero vulnerabilities. Full npm audit: six affected development dependencies (two critical, one high, three moderate). These are unresolved freeze-time tooling debt; npm proposes major Vite/Vitest upgrades. They are not bundled production dependencies; do not expose the dev/test servers to untrusted networks.

Exact advisory IDs from the audit:

- Vitest: GHSA-5xrq-8626-4rwp (UI server arbitrary file read/execution), GHSA-82fw-gwwq-j7x9 (mocker path traversal/arbitrary file read).
- Tinypool: GHSA-5gmw-xhrv-c9v3 and GHSA-85c8-ppgw-ccpr (prototype-pollution gadgets reaching code execution).
- Vite: GHSA-4w7w-66w2-5vf9 (optimized dependency .map traversal), GHSA-v6wh-96g9-6wx3 (Windows UNC/NTLM disclosure), GHSA-fx2h-pf6j-xcff (Windows fs.deny bypass).
- esbuild: GHSA-67mh-4wv8-2f99 (cross-origin development server reads).

Raw reports: /tmp/ghostbuild-qa-npm-full-audit.json, /tmp/ghostbuild-qa-npm-audit.json, /tmp/ghostbuild-qa-python-audit.log. Suite log: /tmp/ghostbuild-qa-final.log. Screenshots and simulator result.json/console.json: /tmp/ghostbuild-release-qa/.

## Final integration follow-up

The combined release fixes the missing original Mac assets and adds prepared-image endpoint/portability regressions. Final core 688, knowledge267 and IKEA88 supersede the baseline counts above; Pi77 and assets41 remain unchanged. Phone tests increased to32 with explicit prepared/live review-label checks. Final focused Chromium checks and live MALM/Prusa correction evidence are summarized in [current release status](../../FINAL_SPRINT_STATUS.md). Operator reports readable physical G2 cues/image, press/swipes, answer return and reconnect passed for the voice-disabled LAN build; the detailed device record remains pending. This is separate from the simulator evidence above.
