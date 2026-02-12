#!/usr/bin/env python3
import json

# GRADING_PROMPT = """Grade this question on a scale of 0–5 for suitability in benchmarking LLM hallucination in Rust code generation. A high score (4–5) means:
# - The question requires writing non-trivial, original Rust code (not just debugging, explaining, or trivial snippets).
# - It must require non-trivial usage of other crates, not just the standard library.
# - However, the crate must be installable and buildable with cargo alone on linux, it must not require usage of C/C++ dependencies, apt installations, windows, macos, or other non-linux platforms libraries, or manual build steps.
# - The solution is complex enough to tempt an LLM into hallucinating APIs, methods, traits, or imports—but still verifiable using `cargo check`.
# - We only focus on hallucinated api calls and methods, we don't care type check, ownership, or logical errors.

# Provide your grade first (0–5), then justify it."""

GRADING_PROMPT = """Answer these following questions about the task above:
1. Does the task require writing non-trivial, original Rust code? 0 for no, 1 for yes
2. Does the task require usage of other crates, not just the standard library? 0 for no, 1 for yes
3. Is the crate installable and buildable with cargo alone on linux without C/C++ dependencies, apt installations, windows, macos, or other non-linux platforms libraries, or manual build steps? 0 for no, 1 for yes

Only return a json object with the following keys:
- non_trivial_rust_code: 0 for no, 1 for yes
- installable_and_buildable: 0 for no, 1 for yes
- other_crates: 0 for no, 1 for yes
- other_crates_list: list of other crates
"""

input_file = "data/rust_questions.jsonl"
output_file = "data/formatted_questions.jsonl"

with open(input_file, 'r', encoding='utf-8') as f_in, \
     open(output_file, 'w', encoding='utf-8') as f_out:
    for line in f_in:
        if not line.strip():
            continue
        question = json.loads(line)
        title = question.get('title', '')
        body = question.get('body', '')
        prompt = f"Task: {title}\n\n {body}\n\nInstruction: {GRADING_PROMPT}"
        
        formatted = {
            "prompt": prompt,
            "question_id": question.get('question_id'),
            "title": title,
            "tags": question.get('tags', []),
            "link": question.get('link', ''),
        }
        
        f_out.write(json.dumps(formatted, ensure_ascii=False) + '\n')
