# 17 — SECURITY, SECRETS AND DEDUCTION ARMOUR

> **Owner:** both · **Continuous** · **Rubric:** F7 (1), H2 (2), I6 (2) — **and all of §5.3 (−101)**
> The eleven automatic deductions total **−101 marks**. The rubric sections they map to total
> far less. **Protecting against deductions is the highest marks-per-hour activity in the
> assignment** (`02-CRITICAL-PATH.md §7`). This file is that protection in one place.

---

## 1. The deduction ledger — every violation, its guard, and its detector

| # | §5.3 violation | Penalty | Primary guard | Automated detector |
|---|---|---|---|---|
| 1 | `.env`, key, token or password **anywhere in git history** | **−20** + rotation + incident note | `.gitignore` before the first `git add`; pre-commit `gitleaks`; `detect-private-key` | `make history-scan` · `check_submission.py::SEC-ENV-HISTORY` |
| 2 | LLM key in a committed k8s manifest, **even base64** | **−15** | `stringData:` with visible `PLACEHOLDER_…`; secrets created at deploy time from GitHub Secrets | `.gitleaks.toml::k8s-secret-nonplaceholder` · `ci.yml::manifests` grep · `SEC-K8S-SECRET` |
| 3 | Unpinned base image, or `postgres`/`redis`/`node` untagged | **−8** | every `FROM` and `image:` carries an explicit minor tag; digests for bonus | `IMG-UNPINNED` regex over Dockerfiles, compose, k8s |
| 4 | `localhost` for service-to-service | **−8** | service names everywhere; `.env.example` ships `POSTGRES_HOST=database` | `make lint-localhost` in pre-commit **and** `lint-and-type` |
| 5 | Frontend able to reach the database | **−8** | `internal: true` + frontend on `edge` only; NetworkPolicy in k8s | `ci.yml::integration` asserts `nc` **fails**; `NET-SEGMENT` parses the compose graph |
| 6 | Published DB/cache port in `compose.prod.yaml`, or NodePort/LB on the DB | **−8** | no `ports:` on `database`/`cache` in prod; all Services ClusterIP | `PORT-EXPOSED-PROD` + `assert_k8s_invariants.py` |
| 7 | Publishing/deploying job not gated by `needs:` | **−8** | `needs: test` / `needs: build-push` | `CI-NEEDS` parses every workflow for publish/deploy verbs |
| 8 | Deploying `:latest` anywhere | **−8** | overlays pinned by `kustomize edit set image` to SHA or digest | `kustomize build \| grep :latest` in `manifests` job · `CD-LATEST-DEPLOY` |
| 9 | Postgres as a Deployment with no PVC | **−8** | StatefulSet + `volumeClaimTemplates` | `K8S-DB-DEPLOYMENT` |
| 10 | Commits pushed directly to `main` | **−5** | branch protection with **"do not allow bypassing"** ticked | `VCS-DIRECT-MAIN` diffs first-parent history against PR merges |
| 11 | README quickstart that fails from a clean clone | **−5** | `make up` is the quickstart; CI `integration` runs it from a fresh checkout | `DOC-QUICKSTART` + the cross-executed clean-clone test at Gate 8 |

**Every row has a detector.** That is the design principle: a rule a human must remember is a rule
you will break at 2 a.m. on day 13. `scripts/check_submission.py` (`03-REPO-BOOTSTRAP.md §8`)
runs all eleven in one command, and it is the last thing you run before submitting (§5.8).

---

## 2. Secret handling by environment

| Environment | Where the secret lives | How it reaches the process | Never |
|---|---|---|---|
| Local dev | `.env` (gitignored) | Compose `${...}` interpolation | committed, pasted in Slack, in a screenshot |
| CI tests | not needed — `TRIAGE_PROVIDER=simulated` | — | a real key in a PR workflow |
| CD deploy | GitHub repository secrets | `kubectl create secret … --dry-run=client -o yaml \| kubectl apply -f -` | `echo`d, written to a file, base64'd in a log |
| Kubernetes | `Secret` object created at deploy time | `envFrom: secretRef` | in a committed manifest, even base64 |
| Container image | **nowhere** | — | `ENV LLM_API_KEY=` in a Dockerfile — it is in the layer forever |
| Browser bundle | **nowhere** | — | §2.1: *"anything in a browser bundle is public, and 'it's minified' is not a defence"* |

**In-process handling:** `SecretStr` on `Settings.llm_api_key` (`06-BACKEND-CORE.md §1`) means
`repr()`, `model_dump()` and a FastAPI validation-error dump all print `**********`.
A `logging.Filter` additionally redacts `gsk_[A-Za-z0-9]{20,}` and `AIza[\w-]{35}` from any
formatted message. Two independent layers, because §2.5 item 6 is absolute: *"Never log the API
key."*

Test: `test_api_key_never_logged` (F21) drives a full request cycle with a fake key and asserts the
prefix appears in **zero** captured log records, **zero** metric labels, and **zero** response bodies.

---

## 3. Incident runbook — a secret reached the repository

> §5.3 does not just penalise the exposure; it requires that *"you must rotate the credential and
> write an incident note."* Doing the rotation and the note well is how you recover some credibility
> even while taking the −20.

**Do these in order. Do not skip step 1 to "clean up first" — the key is live while you rewrite.**

1. **Rotate immediately, before touching git.** Groq console → revoke → issue new. Google AI
   Studio → delete key → create. Postgres → `ALTER USER … PASSWORD`. Record the UTC timestamp.
2. **Assess blast radius.** Was the repo public? For how long? Push events are indexed by
   third-party scanners within **seconds** of a public push — assume compromise, not "probably
   fine". Check the provider's usage dashboard for calls you did not make.
3. **Rewrite history**, with the partner offline and both of you present:
   ```bash
   pip install git-filter-repo
   git clone --mirror git@github.com:ORG/civicpulse.git /tmp/cp.git
   cd /tmp/cp.git
   git filter-repo --invert-paths --path .env --path backend/.env --force
   # or, for a key embedded in a tracked file:
   git filter-repo --replace-text <(echo 'gsk_REDACTED_LITERAL==>***REMOVED***')
   git push --force --mirror
   ```
4. **Both developers re-clone.** Do not `git pull` into an old clone — the old objects come back on
   the next push and you have undone the rewrite.
5. **Invalidate caches you do not control.** GitHub keeps unreachable objects accessible by SHA for
   a period and forks retain them. Open a GitHub Support request to expire the cached views, and
   **say in the note that you did**, because this is the part most people do not know.
6. **Write `docs/evidence/incident-secret-exposure.md`:**
   ```markdown
   # Incident: credential exposure
   Detected:  2026-09-21T14:03Z by pre-push gitleaks (commit 4f1a2b9)
   Exposed:   GROQ_API_KEY (prefix gsk_9xK…), committed 2026-09-21T11:47Z in `backend/.env`
   Window:    2h16m, repository private throughout (0 forks, 2 collaborators)
   Rotated:   2026-09-21T14:09Z — old key revoked, new key issued, GitHub Secret updated
   Blast:     provider usage dashboard shows 41 calls in the window, all from our CI runner IPs
   Remediation: git-filter-repo --invert-paths --path backend/.env; force-push; both clones recreated
   Prevention: .gitignore hardened, gitleaks added to pre-commit AND to ci.yml, .env.example is the
               only env file that may be tracked, `make secret-scan` added to `make check`
   Root cause: `.env` was created before `.gitignore` was committed (Gate 0 ordering violation)
   ```
7. **Close the loop in the process**, not just the repo: move the `.gitignore` commit to the *first*
   commit of the project (Gate 0 exists for this), and add the pre-commit hook to the bootstrap.

> The root-cause line matters most. *"We forgot"* is not a root cause; *"the ordering of Gate 0 let
> `.env` exist before `.gitignore` did"* is, and it names the fix.

---

## 4. ADR-0004 — PII and data governance (Rubric F, 1 mark; Rubric J, part of 4)

> §2.5 on Gemini's free tier: *"Google may use your inputs to improve its models. Citizen complaints
> contain names, addresses and phone numbers. Write the resulting PII decision into an ADR…
> a thoughtful ADR here is worth more in an interview than the entire rest of the repository."*

### 4.1 Data inventory — what we hold

| Field | PII? | Sensitivity | Retention |
|---|---|---|---|
| `text` | **Yes, unstructured** — citizens embed names, house numbers, CNIC digits, phone numbers | High. The worst case is an unstructured field: you cannot enumerate what is in it | Indefinite in v1; §4.4 proposes a policy |
| `location` | **Yes** — street-level, often a home address | High | Indefinite |
| `reporter_contact` | **Yes** — phone or email, directly identifying | High | Indefinite |
| `ai_summary` | **Derived PII** — the model may copy a name into it | High | Indefinite |
| `category`, `priority`, `status` | No | Low | — |
| `triaged_by`, `triage_latency_ms`, `triage_confidence` | No | Low | — |
| `request_id` | No, but a **linkage key** to logs | Medium | log retention |

### 4.2 What leaves the machine, to whom

| Destination | Payload | Controls |
|---|---|---|
| Hosted LLM (Groq/Gemini) | `text` + `location` only. **Not** `reporter_contact`, **not** `id`, **not** `request_id` | The prompt builder takes exactly two arguments (`08-AI-TRIAGE.md §1`) — the contact field is structurally unable to reach it |
| Ollama (local) | same two fields | Never leaves the host. **This is the zero-egress option.** |
| Logs (stdout) | `text_len`, never `text` | `06-BACKEND-CORE.md §3.2` |
| Metrics | no free text, no identifiers as labels | cardinality rule, `10-OBSERVABILITY.md §1.2` |
| Traces (bonus) | span attributes exclude all PII | `10-OBSERVABILITY.md §6` |
| `/api/meta/providers` | ids and timings only, never text | test `test_meta_providers_leaks_nothing` |

**The structural control is the important one:** `triage(text, location)` cannot leak
`reporter_contact` because it is never passed. That is safety by interface design, not by
discipline — and it is the ADR's strongest sentence.

### 4.3 The decision

**Context.** Free-tier Gemini may use inputs for model improvement. Free-tier Groq's terms differ
and must be read and cited on the date checked (§2.5: *"cite what you actually saw"*, and
contradiction A12 — the brief's own provider claims are second-hand). Complaint text is
unstructured citizen PII.

**Options considered:**

| Option | Privacy | Quality | Ops cost | Verdict |
|---|---|---|---|---|
| A — Send raw text to a hosted free tier | Worst. Unbounded unstructured PII to a third party that may train on it | Best | Lowest | **Rejected** as the default |
| B — Redact before sending (regex: phone, email, CNIC, long digit runs) then hosted | Better. Bounded, but regex redaction on Urdu-influenced English will miss names and will damage some complaints | Slightly reduced (redaction removes context) | Low | **Accepted for the hosted path** |
| C — Ollama locally, nothing leaves the host | Best. Zero egress | Measurably worse (`docs/TRIAGE.md §4`) | Highest (4 GB RAM, slow CPU inference) | **Accepted as the default for any deployment handling real citizen data** |
| D — Consent + notice at submission time | Best legally | Unchanged | Requires UI + policy | **Deferred**, named as the next step |

**Decision.** The default configuration for anything resembling real data is **C (Ollama)**. The
hosted path is **B**: `redact_pii()` runs before prompt construction, removing phone-shaped
sequences, email addresses and digit runs ≥ 9, replacing each with a typed token
(`[PHONE]`, `[EMAIL]`, `[ID]`). `reporter_contact` is never sent under any configuration.
The demo video uses seed data containing **no real personal data** (`05-DATA-LAYER.md §6.2`).

**Consequences.** Redaction slightly reduces classification context; measured on the golden set,
agreement drops by a small margin, and that margin is reported in `docs/TRIAGE.md`. The system
retains an unredacted copy in Postgres — redaction is a *transmission* control, not a *storage*
control, and the ADR says so plainly rather than implying more protection than exists.

**Honest limitations, stated:** regex redaction does not remove names; it does not remove
identifying combinations of street and landmark; and a determined re-identification attack against
a municipal dataset would succeed. This system is a coursework artefact and a production
deployment would need a DPIA, a retention policy, an access-control model over the dashboard,
and a lawful basis for processing. **Naming what you did *not* solve is what makes an ADR
credible.**

### 4.4 Proposed retention policy (deferred, documented)

`created_at + 24 months` → delete `reporter_contact`, keep the anonymised row for statistics.
Implemented as a migration plus a scheduled job; out of scope for v1, tracked as Issue #N.

---

## 5. Supply chain

| Control | Implementation | Rubric |
|---|---|---|
| Pinned base images | explicit minor tags; `scripts/pin_digests.sh` for digest pinning | G, §5.3 −8 |
| Pinned dependencies | `requirements.lock` (hashes), `package-lock.json` committed, `npm ci` not `npm install` | G |
| Pinned actions | `@v4` minimum, SHA for bonus | I |
| Vulnerability scan | Trivy HIGH/CRITICAL, `ignore-unfixed: true`, SARIF to the Security tab | I3 |
| SBOM | Syft SPDX-JSON per image, attached to the release | I4, bonus |
| Signing | Cosign keyless (OIDC), verified **before** deploy | bonus +3 |
| Provenance | `provenance: true` on build-push; OCI labels via `metadata-action` | bonus |
| Least privilege in CI | `permissions` at workflow + job level | I6 |

**`ignore-unfixed: true` is defensible, and the defence matters more than the flag:** a HIGH with
no upstream fix is information, not an action. Failing on it leaves only two paths — pin to a
vulnerable-but-quiet base, or disable the scanner — and both are worse than an accurate report.
`.trivyignore` entries each carry a justification **and an expiry date**; an entry past its expiry
fails the build.

---

## 6. Runtime hardening (cheap, and it reads as production experience)

```yaml
securityContext:                  # pod level
  runAsNonRoot: true
  runAsUser: 10001
  fsGroup: 10001
  seccompProfile: {type: RuntimeDefault}
containers:
  - securityContext:              # container level
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities: {drop: ["ALL"]}
```

| Control | Blocks |
|---|---|
| `runAsNonRoot` + uid 10001 | a container escape landing as uid 0 in the node namespace |
| `readOnlyRootFilesystem` | an attacker writing a webshell or a crypto miner into the image layer. Requires an `emptyDir` at `/tmp` — which we mount |
| `drop: ["ALL"]` | `CAP_NET_RAW` (packet crafting), `CAP_SYS_PTRACE`, etc. Nothing in a FastAPI app needs a capability |
| `allowPrivilegeEscalation: false` | `setuid` binaries gaining privileges mid-process |
| `seccompProfile: RuntimeDefault` | the long tail of unused syscalls |

**Application-level:** `extra="forbid"` on input models (no mass-assignment), parameterised SQL
only (SQLAlchemy Core — never string-built, and **never built from model output**, §2.5),
`page_size ≤ 100` (no unbounded result sets), 2 MB request body cap at nginx, security headers
(`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`) from the frontend nginx, and
opaque 500 bodies that leak no stack trace (`06-BACKEND-CORE.md §7`).

**Deliberately out of scope, and say so:** there is **no authentication** on the operator dashboard.
The spec does not ask for it, and inventing a half-auth system would be worse than none. Name it
in the README's "Known limitations": *"the dashboard is unauthenticated; a production deployment
needs an operator identity provider and per-role authorisation on `PATCH /status`."* Knowing the
gap is the mark of someone who has shipped; pretending it is not there is not.

---

## 7. Pre-submission security sweep

```bash
make history-scan                                   # gitleaks over --all refs
git log --all --diff-filter=A --name-only | grep -E '(^|/)\.env$|\.pem$|\.key$' && echo "FAIL"
grep -rniE 'gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}' . \
  --exclude-dir={.git,node_modules,docs} && echo "FAIL"
kustomize build k8s/overlays/prod | grep -iE 'api[_-]?key|password' | grep -v PLACEHOLDER && echo "FAIL"
grep -rn "ENV .*\(KEY\|PASSWORD\|TOKEN\)" */Dockerfile && echo "FAIL"
docker run --rm -it --entrypoint sh civicpulse-backend:ci -c 'env | grep -i key'   # empty
docker history civicpulse-backend:ci --no-trunc | grep -i 'key\|password' && echo "FAIL"
python scripts/check_submission.py
```

`docker history` is the one people forget: a secret passed as a build `ARG` and used in a `RUN` is
**visible in the image metadata forever**, even though it is not in the final filesystem. The only
safe build-time secret is a BuildKit `--mount=type=secret`, which never lands in a layer. We do
not need one — nothing in either build requires a credential — and that fact is itself worth stating.
