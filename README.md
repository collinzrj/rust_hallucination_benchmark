# Rust Code Hallucination Benchmark

A benchmark for evaluating LLM hallucinations in Rust code generation. This benchmark measures how often language models generate non-existent APIs, methods, imports, or crate features when asked to solve programming tasks.

## Overview

When generating code, LLMs sometimes "hallucinate" - they invent APIs, methods, or imports that don't actually exist. This benchmark:

1. Collects real Rust programming questions from Stack Overflow
2. Asks LLMs to generate complete, runnable solutions
3. Verifies the generated code with `cargo check`
4. Analyzes compilation errors to identify hallucinated API usage

## Hallucination Types Detected

| Type | Description | Example Error Code |
|------|-------------|-------------------|
| **Method** | Non-existent methods/functions | `E0599: no method named 'X' found` |
| **Import** | Non-existent types, crates, or modules | `unresolved import`, `use of undeclared type` |
| **Feature** | Non-existent crate features | `cargo-build-failure: does not have that feature` |

## Benchmark Results

| Model | Method Hallucination | Import Hallucination | Feature Hallucination | Any Hallucination |
|-------|---------------------|---------------------|----------------------|-------------------|
| gpt-5.2-2025-12-11 | 4/69 (5.80%) | 6/69 (8.70%) | 2/69 (2.90%) | 12/69 (17.39%) |
| qwen3-coder-30b-a3b-instruct | 8/69 (11.59%) | 10/69 (14.49%) | 1/69 (1.45%) | 16/69 (23.19%) |
| qwen3-max-2026-01-23 | 8/69 (11.59%) | 14/69 (20.29%) | 3/69 (4.35%) | 22/69 (31.88%) |
| gpt-5.2-codex | 8/68 (11.76%) | 7/68 (10.29%) | 4/68 (5.88%) | 17/68 (25.00%) |
| google/gemini-3-pro-preview | 6/69 (8.70%) | 7/69 (10.14%) | 4/69 (5.80%) | 16/69 (23.19%) |
| openai/gpt-5.2 | 25/345 (7.25%) | 31/345 (8.99%) | 14/345 (4.06%) | 68/345 (19.71%) |
| qwen3-max-2026-01-23 | 39/345 (11.30%) | 61/345 (17.68%) | 13/345 (3.77%) | 99/345 (28.70%) |
| anthropic/claude-opus-4.6 | 16/345 (4.64%) | 65/345 (18.84%) | 6/345 (1.74%) | 80/345 (23.19%) |
| z-ai/glm-5 | 28/345 (8.12%) | 61/345 (17.68%) | 7/345 (2.03%) | 85/345 (24.64%) |
| deepseek/deepseek-r1 | 43/345 (12.46%) | 62/345 (17.97%) | 32/345 (9.28%) | 123/345 (35.65%) |
| qwen/qwen3.5-plus-02-15 | 39/345 (11.30%) | 61/345 (17.68%) | 10/345 (2.90%) | 93/345 (26.96%) |
| qwen3.5-plus | 45/345 (13.04%) | 58/345 (16.81%) | 6/345 (1.74%) | 94/345 (27.25%) |

## Pipeline

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Stack Overflow API │────▶│  Format Questions    │────▶│  Filter Questions   │
│  (get_stackoverflow)│     │  (format_question)   │     │  (filter_questions) │
└─────────────────────┘     └──────────────────────┘     └─────────────────────┘
                                                                  │
                                                                  ▼
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Hallucination      │◀────│  Analyze Errors      │◀────│  Cargo Check        │
│  Analysis           │     │  (analyze_hallucin.)  │     │  (grade.py)         │
└─────────────────────┘     └──────────────────────┘     └─────────────────────┘
                                      ▲
                                      │
                        ┌──────────────────────┐
                        │  LLM Response        │
                        │  (concurrent_api)    │
                        └──────────────────────┘
```

## Installation

### Prerequisites

- Python 3.8+
- Rust and Cargo (for `cargo check`)
- Conda (recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/rust-code-hallucination-benchmark.git
cd rust-code-hallucination-benchmark

# Create conda environment
conda create -n code_hallucination python=3.10
conda activate code_hallucination

# Install Python dependencies
pip install requests json-repair tqdm openai
```

## Usage

### Step 1: Collect Questions from Stack Overflow

Fetch Rust-related questions from Stack Overflow API:

```bash
python get_stackoverflow.py
```

This creates `rust_questions.jsonl` with raw question data.

**Output format:**
```json
{"question_id": 123, "title": "...", "body": "...", "tags": ["rust"], ...}
```

### Step 2: Format Questions for Grading

Add grading prompt to each question:

```bash
python preprocess/format_stackoverflow_question.py
```

This creates `data/formatted_questions.jsonl` with prompts asking an LLM to evaluate question suitability.

### Step 3: Filter Questions

Filter questions through an LLM to select only those that:
1. Require non-trivial Rust code
2. Require external crates (not just std library)
3. Use crates that are installable via `cargo` alone on Linux

First, run your LLM on `data/formatted_questions.jsonl`:

```bash
python concurrent_api_calls.py \
    --model your-model-name \
    --base-url https://your-api-endpoint \
    --input data/formatted_questions.jsonl \
    --output data/graded_questions.jsonl
```

Then filter based on the grading results:

```bash
python preprocess/filter_stackoverflow_questions.py
```

This creates `data/rust_hallucination_questions.jsonl` - the final benchmark dataset.

### Step 4: Generate Code Responses

Ask LLMs to generate complete Rust solutions (Cargo.toml + main.rs):

```bash
python concurrent_api_calls.py \
    --model your-model-name \
    --base-url https://your-api-endpoint \
    --input data/rust_hallucination_questions.jsonl \
    --output data/responses.jsonl \
    --max-concurrent 10
```

**Expected prompt format:** The input should ask for a JSON response with `Cargo.toml` and `main.rs` keys.

### Step 5: Run Cargo Check

Verify generated code with `cargo check`:

```bash
python grade.py
```

Edit the script to point to your response file:
```python
path = "data/responses.jsonl"
report = evaluate_jsonl_parallel(
    path,
    offline=False,  # Set to True if dependencies are cached
    timeout_s=360,
    num_workers=32
)
```

This creates `responses.jsonl.cargo_check_report.json`.

### Step 6: Analyze Hallucinations

Analyze cargo check errors to identify hallucinated APIs:

```bash
python analyze_hallucinations.py data/responses.jsonl.cargo_check_report.json
```

This creates `responses.jsonl.hallucination_analysis.json` with detailed hallucination statistics.

### Step 7: Compare Results

Compare hallucination rates across models:

```bash
python utils/compare_hallu.py
```

Edit the `paths` variable in the script to point to your analysis files.

## Project Structure

```
.
├── get_stackoverflow.py        # Fetch questions from Stack Overflow API
├── concurrent_api_calls.py    # Make parallel LLM API calls with caching
├── grade.py                   # Run cargo check on generated code
├── analyze_hallucinations.py  # Analyze errors for hallucinations
├── preprocess/
│   ├── format_stackoverflow_question.py  # Add grading prompts
│   └── filter_stackoverflow_questions.py # Filter by grading criteria
├── utils/
│   ├── compare_hallu.py       # Compare hallucination rates across models
│   └── search_code.py
└── data/                      # Data files (git-ignored)
    ├── rust_questions.jsonl
    ├── formatted_questions.jsonl
    ├── rust_hallucination_questions.jsonl
    └── *.jsonl.cargo_check_report.json
```

## Hallucination Detection Logic

The analyzer detects hallucinations based on Rust compiler error codes:

| Error Pattern | Hallucination Type |
|---------------|-------------------|
| `E0599`: no method named X found | Method |
| `no function named X found` | Method |
| `unresolved import X` | Import |
| `use of undeclared type X` | Import |
| `use of unresolved module or unlinked crate X` | Import |
| `does not have that feature` | Feature |

**Exclusions:** Errors about trait bounds not satisfied or methods from traits not in scope are NOT counted as hallucinations, as the methods may exist but require additional imports.

## Adding New Models

To evaluate a new model:

1. Generate responses using `concurrent_api_calls.py`
2. Run `grade.py` on the output
3. Run `analyze_hallucinations.py` on the cargo check report
4. Add the analysis file path to `utils/compare_hallu.py`

## Citation

If you use this benchmark, please cite:

```bibtex
@misc{rust-hallucination-benchmark,
  title={Rust Code Hallucination Benchmark},
  author={Your Name},
  year={2025}
}
```

## License

MIT License