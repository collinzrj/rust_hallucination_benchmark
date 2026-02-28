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
| openai/gpt-5.2 | 25/345 (7.25%) | 31/345 (8.99%) | 14/345 (4.06%) | 68/345 (19.71%) |
| anthropic/claude-opus-4.6 | 16/345 (4.64%) | 65/345 (18.84%) | 6/345 (1.74%) | 80/345 (23.19%) |
| z-ai/glm-5 | 28/345 (8.12%) | 61/345 (17.68%) | 7/345 (2.03%) | 85/345 (24.64%) |
| deepseek/deepseek-r1 | 43/345 (12.46%) | 62/345 (17.97%) | 32/345 (9.28%) | 123/345 (35.65%) |
| qwen3-max-2026-01-23 | 39/345 (11.30%) | 61/345 (17.68%) | 13/345 (3.77%) | 99/345 (28.70%) |
| qwen/qwen3.5-plus-02-15 | 39/345 (11.30%) | 61/345 (17.68%) | 10/345 (2.90%) | 93/345 (26.96%) |

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

## Provided Data

We provide pre-processed data so you can skip steps and directly evaluate your models:

| File | Description |
|------|-------------|
| `data/rust_questions.jsonl` | Raw Stack Overflow questions (500 questions) |
| `data/formatted_questions_output_20260206_153818.jsonl` | Questions formatted with grading prompts |
| `data/rust_hallucination_questions.jsonl` | **Final benchmark dataset** (69 filtered questions) |

### LLM Responses & Analysis Results

We include responses from multiple models with their cargo check reports and hallucination analysis:

```
data/rust_hallucination_questions_output_*.jsonl           # LLM responses
data/rust_hallucination_questions_output_*.jsonl.cargo_check_report.json     # Cargo check results
data/rust_hallucination_questions_output_*.jsonl.hallucination_analysis.json  # Hallucination analysis
```

### Quick Start: Using Provided Data

To evaluate a new model on our benchmark:

```bash
# Generate responses for your model
python concurrent_api_calls.py \
    --model your-model-name \
    --base-url https://your-api-endpoint \
    --input data/rust_hallucination_questions.jsonl \
    --output data/your_model_responses.jsonl

# Run cargo check
python grade.py data/your_model_responses.jsonl

# Analyze hallucinations
python analyze_hallucinations.py data/your_model_responses.jsonl.cargo_check_report.json

# Compare with existing results
# Add your analysis file path to utils/compare_hallu.py
python utils/compare_hallu.py
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

## Full Pipeline: Recreating the Benchmark

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
python grade.py data/your_model_responses.jsonl [--offline] [--timeout 360] [--workers 32]
```

**Arguments:**
- `input` - Input JSONL file with LLM responses (required)
- `--offline` - Use offline mode for cargo (use cached dependencies)
- `--timeout` - Timeout per sample in seconds (default: 360)
- `--workers` - Number of parallel workers (default: CPU count)

This creates `data/your_model_responses.jsonl.cargo_check_report.json`.

### Step 6: Analyze Hallucinations

Analyze cargo check errors to identify hallucinated APIs:

```bash
python analyze_hallucinations.py data/your_model_responses.jsonl.cargo_check_report.json
```

This creates `your_model_responses.jsonl.hallucination_analysis.json` with detailed hallucination statistics.

### Step 7: Compare Results

Compare hallucination rates across models by adding your analysis file to `utils/compare_hallu.py`:

```python
paths = """
data/your_model_responses.jsonl.hallucination_analysis.json
""".split("\n")
```

Then run:

```bash
python utils/compare_hallu.py
```

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
└── data/
    ├── rust_questions.jsonl                        # Raw Stack Overflow questions
    ├── formatted_questions_output_*.jsonl          # Graded questions
    ├── rust_hallucination_questions.jsonl          # Final benchmark (69 questions)
    ├── rust_hallucination_questions_output_*.jsonl # LLM responses
    ├── *_output_*.jsonl.cargo_check_report.json    # Cargo check results
    └── *_output_*.jsonl.hallucination_analysis.json # Hallucination analysis
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

## License

MIT License