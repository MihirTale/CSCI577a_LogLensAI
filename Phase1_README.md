# CSCI-577a-Sample-App

CSCI-577a: Sample App which LogLens Agent will monitor.

This repository contains five CI/CD pipelines, each deliberately triggering a different class of real-world error. Each pipeline runs its simulation script, captures the output, and finishes with an AI-powered analysis step that opens a GitHub issue with a root-cause breakdown.
This is a new feature.
---

## Repository Structure

```
.github/
  workflows/
    pipeline-oom.yml            # Pipeline 1 – Out-of-Memory
    pipeline-type-error.yml     # Pipeline 2 – Type Error
    pipeline-missing-env.yml    # Pipeline 3 – Missing Environment Variable
    pipeline-dep-conflict.yml   # Pipeline 4 – Dependency Conflict
    pipeline-flaky-test.yml     # Pipeline 5 – Flaky Integration Test
  actions/
    ai-error-analyzer/
      action.yml                # Composite action definition
      analyze_and_create_issue.py  # AI analysis + GitHub issue creation
scripts/
  simulate_oom.py
  simulate_type_error.py
  simulate_missing_env.py
  simulate_dep_conflict.py
  simulate_flaky_test.py
```

---

## Simulation Scripts

### 1. `simulate_oom.py` — Out-of-Memory Error

**Pipeline:** `pipeline-oom.yml`

**Error:** `numpy.core._exceptions.MemoryError`

Installs NumPy at runtime, then attempts to allocate a `(10,000,000,000 × 1,000)` float64 array (~80 TB). NumPy's own memory allocator raises the error — no fake `raise` statement is used.

```
MemoryError: Unable to allocate 80.0 TiB for an array
with shape (10000000000, 1000) and data type float64
```

**Real-world scenario:** A data loader reads an entire multi-gigabyte CSV into RAM instead of streaming it in chunks, exhausting the runner's available memory.

---

### 2. `simulate_type_error.py` — Type Error

**Pipeline:** `pipeline-type-error.yml`

**Error:** `TypeError`

Passes a mixed-type list (floats and string sentinels like `"N/A"`, `"ERROR"`, `"OFFLINE"`) to Python's built-in `sum()`. Python's own runtime raises the error.

```
TypeError: unsupported operand type(s) for +: 'float' and 'str'
```

**Real-world scenario:** An IoT sensor gateway inserts string placeholders for missing readings instead of `NaN`, causing downstream numeric aggregation to crash.

---

### 3. `simulate_missing_env.py` — Missing Environment Variable

**Pipeline:** `pipeline-missing-env.yml`

**Error:** `KeyError`

Reads four required environment variables using `os.environ[key]` (bracket notation). Because none of `MODEL_SERVING_ENDPOINT`, `MODEL_API_SECRET_KEY`, `INFERENCE_TIMEOUT_MS`, or `FEATURE_STORE_DSN` are set on the runner, Python's dictionary raises the error natively.

```
KeyError: 'MODEL_SERVING_ENDPOINT'
```

**Real-world scenario:** Secrets or config values exist in a developer's local `.env` file but were never added to the CI secrets store, causing a hard crash the first time the pipeline runs in a fresh environment.

---

### 4. `simulate_dep_conflict.py` — Dependency Version Conflict

**Pipeline:** `pipeline-dep-conflict.yml`

**Error:** `ImportError` (C-ABI mismatch)

Uses `pip` to install `pandas==2.1.4` (whose C-extensions are compiled against the NumPy 1.x ABI), then force-reinstalls `numpy==2.0.0` (which introduced breaking C-ABI changes). Importing `pandas` afterwards fails because Python's dynamic linker cannot resolve symbols that were renamed or removed in NumPy 2.0.

```
ImportError: .../pandas/_libs/lib.cpython-311-x86_64-linux-gnu.so:
    undefined symbol: _PyArray_LegacyDescr
```

**Real-world scenario:** Two packages in `requirements.txt` have conflicting constraints on a shared transitive dependency. The resolver picks a version that satisfies one package but breaks the other.

---

### 5. `simulate_flaky_test.py` — Flaky Integration Test (Race Condition)

**Pipeline:** `pipeline-flaky-test.yml`

**Error:** `AssertionError`

Spawns ten `threading.Thread` workers, each sleeping for a different duration to simulate varying processing times. Because threads finish in order of their sleep duration — not their submission order — `assert completion_order == input_ids` fails with Python's own assertion machinery. No hardcoded out-of-order list is used; the race is genuine every run.

```
AssertionError: Prediction order mismatch!
  Expected : ['req-000', 'req-001', ..., 'req-009']
  Got      : ['req-001', 'req-003', 'req-000', ...]
```

**Real-world scenario:** An async batch API emits results as each worker finishes rather than in submission order. Tests that assert deterministic ordering pass locally (where the machine is fast and consistent) but fail unpredictably on CI where worker-pool sizes and scheduler behaviour differ.

---

## AI Error Analysis

Every pipeline shares a final step powered by the `.github/actions/ai-error-analyzer` composite action. After the simulation step fails, this action:

1. Reads the captured `pipeline_errors.log`
2. Sends the log to an AI model (Google Gemini by default, or Anthropic Claude)
3. Parses the response to extract an issue title and body
4. Opens a GitHub issue labelled `bug`, `ai-analysis`, and `pipeline-failure`

### Configuration

| Secret / Input | Where to set it | Description |
|---|---|---|
| `AI_API_KEY` | GitHub → Settings → Environments → `AI_API_KEY` → Secrets | API key for Gemini or Claude |
| `GITHUB_TOKEN` | Provided automatically by GitHub Actions | Used to create issues; issues appear as `github-actions[bot]` |
| `ai-model` (optional) | `workflow_dispatch` input | Model ID, e.g. `gemini-2.0-flash` or `claude-3-5-sonnet-20241022`. Defaults to `gemini-2.0-flash` if omitted. Provider is inferred from the model name. |

### Triggering a Pipeline Manually

1. Go to **Actions** in your repository
2. Select a pipeline (e.g. `Pipeline - OOM Error`)
3. Click **Run workflow**
4. Optionally enter a model ID — leave blank for the Gemini default
5. The pipeline will fail at the simulation step and automatically open a GitHub issue with the AI analysis

