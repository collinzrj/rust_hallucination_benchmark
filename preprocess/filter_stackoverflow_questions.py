#!/usr/bin/env python3
import json
import re

input_file = "/share/shmatikov/collin/code_hallucination/data/formatted_questions_output_20260206_153818.jsonl"
# output_file = input_file.replace('.jsonl', '_filtered.jsonl')
output_file = "/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions.jsonl"

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

# Read all lines first, then write back
data_to_write = []

with open(input_file, 'r', encoding='utf-8') as f_in:
    for line in f_in:
        if not line.strip():
            continue
        
        data = json.loads(line)
        response = data.get('response', '')
        
        # Extract score using heuristic
        res = json.loads(response)
        ok = res.get('non_trivial_rust_code', 0) == 1 and res.get('installable_and_buildable', 0) == 1 and res.get('other_crates', 0) == 1
        if ok:
            data['prompt'] = data['prompt'].replace(GRADING_PROMPT, "Your deliverables is a Cargo.toml file and a main.rs file that's self-contained so I can move them into a rust project and test it with `cargo run`. Only return a json object with the following keys: - Cargo.toml: the contents of the Cargo.toml file - main.rs: the contents of the main.rs file")
            data_to_write.append(data)

with open(output_file, 'w', encoding='utf-8') as f_out:
    for data in data_to_write:
        line = json.dumps(data, ensure_ascii=False)
        f_out.write(line + '\n')