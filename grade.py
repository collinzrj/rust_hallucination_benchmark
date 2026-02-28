import os
import re
import json, json_repair
import tempfile
import subprocess
import multiprocessing
from typing import List, Dict, Any, Optional
from tqdm import tqdm


# ----------------------------
# 1) Extract Cargo.toml + src/main.rs from LLM text
# ----------------------------
def extract_cargo_and_main(llm_text: str) -> List[Dict[str, str]]:
    """
    Best-effort extraction of ONLY:
      - Cargo.toml
      - src/main.rs (or main.rs)
    from varied LLM markdown.
    """
    original_llm_text = llm_text
    data: Dict[str, Any] = {}
    if '```json' in llm_text:
        pattern = r"```json\s*\n(.*?)\n```"
        blocks = re.findall(pattern, llm_text, re.DOTALL)
        for block in blocks:
            try:
                parsed = json_repair.loads(block)
            except Exception:
                continue
            if isinstance(parsed, dict):
                data.update(parsed)
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        data.update(item)
    else:
        try:
            data = json_repair.loads(llm_text)
        except Exception:
            print(f"Failed to parse JSON: {[llm_text]}")
    
    if "Cargo.toml" not in data or "main.rs" not in data:
        data = {}
        if ('```toml' in original_llm_text or '```ini' in original_llm_text) and '```rust' in original_llm_text:
            toml_pattern = r"```(?:toml|ini)\s*\n(.*?)\n```"
            rust_pattern = r"```rust\s*\n(.*?)\n```"
            toml_match = re.search(toml_pattern, original_llm_text, re.DOTALL)
            rust_match = re.search(rust_pattern, original_llm_text, re.DOTALL)
            if toml_match and rust_match:
                data["Cargo.toml"] = toml_match.group(1)
                data["main.rs"] = rust_match.group(1)
        else:
            print(f"Failed to find Cargo.toml or main.rs in: {[llm_text]}")

    out = []
    if "Cargo.toml" in data:
        if type(data["Cargo.toml"]) is not str:
            if 'content' in data["Cargo.toml"]:
                data["Cargo.toml"] = data["Cargo.toml"]['content']
            else:
                return []
        out.append({"name": "Cargo.toml", "content": data["Cargo.toml"]})
    if "main.rs" in data:
        if type(data["main.rs"]) is not str:
            if 'content' in data["main.rs"]:
                data["main.rs"] = data["main.rs"]['content']
            else:
                return []
        out.append({"name": "src/main.rs", "content": data["main.rs"]})
    return out


# ----------------------------
# 2) cargo check --message-format=json
# ----------------------------
def cargo_check_json(
    files: List[Dict[str, str]],
    *,
    offline: bool = True,
    timeout_s: int = 180,
) -> Dict[str, Any]:
    """
    Writes Cargo.toml + src/main.rs into a temp dir, runs:
      cargo check --message-format=json
    """
    by_name = {x["name"]: x["content"] for x in files}
    if "Cargo.toml" not in by_name or "src/main.rs" not in by_name:
        return {"status": "missing_files", "returncode": None, "errors": [], "error_count": 0, "raw_stderr": ""}

    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "src"), exist_ok=True)
        with open(os.path.join(d, "Cargo.toml"), "w", encoding="utf-8") as f:
            if type(by_name["Cargo.toml"]) is not str:
                print(by_name["Cargo.toml"])
            f.write(by_name["Cargo.toml"])
        with open(os.path.join(d, "src", "main.rs"), "w", encoding="utf-8") as f:
            f.write(by_name["src/main.rs"])

        env = dict(os.environ)
        if offline:
            env["CARGO_NET_OFFLINE"] = "true"

        # NOTE: If running massive parallel jobs, ensure CARGO_TARGET_DIR 
        # is unique per process or just use the temp dir (default behavior).
        # Since we are in a temp dir per job, we are safe.

        cmd = ["cargo", "check", "--message-format=json"]
        try:
            p = subprocess.run(
                cmd,
                cwd=d,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "returncode": None, "errors": [], "error_count": 0, "raw_stderr": ""}
        
        # We skip logging to "all_cargo.log" inside the worker to avoid write contention/locks.
        # If logging is needed, return the log string and write it in the main process.

        errors = []
        for line in p.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if obj.get("reason") != "compiler-message":
                continue

            msg = obj.get("message", {})
            if msg.get("level") != "error":
                continue

            err = {
                "code": (msg.get("code") or {}).get("code"),
                "message": msg.get("message"),
                "rendered": msg.get("rendered"),
                "spans": msg.get("spans", []),
                "target": (obj.get("target") or {}).get("name"),
                "package_id": obj.get("package_id"),
            }
            errors.append(err)

        if p.returncode != 0 and len(errors) == 0:
            stderr_stripped = p.stderr.strip() if p.stderr else "Unknown cargo failure"
            errors.append({
                "code": "cargo-build-failure",
                "message": stderr_stripped,
                "rendered": stderr_stripped,
                "spans": [],
                "target": "cargo",
                "package_id": None
            })

        status = "ok" if p.returncode == 0 else "compile_fail"
        
        return {
            "status": status,
            "returncode": p.returncode,
            "errors": errors,
            "error_count": len(errors),
            "raw_stderr": p.stderr,
        }


# ----------------------------
# 3) Worker wrapper for Multiprocessing
# ----------------------------
def process_one_line(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker function to process a single JSONL line.
    args: {
      "line_str": str, 
      "line_idx": int, 
      "offline": bool, 
      "timeout_s": int
    }
    """
    line_str = args["line_str"]
    line_idx = args["line_idx"]
    offline = args["offline"]
    timeout_s = args["timeout_s"]

    row = json.loads(line_str)
    llm_text = row["response"]
    if '</think>' in llm_text:
        llm_text = llm_text.split('</think>')[1]
    
    files = extract_cargo_and_main(llm_text)
    res = cargo_check_json(files, offline=offline, timeout_s=timeout_s)
    
    # Return the full result plus the index so we can re-order if needed 
    # (though typically not strictly necessary for just counting)
    res["index"] = line_idx
    return res


# ----------------------------
# 4) Parallel Orchestrator
# ----------------------------
def evaluate_jsonl_parallel(
    path: str,
    *,
    offline: bool = True,
    timeout_s: int = 180,
    limit: Optional[int] = None,
    num_workers: Optional[int] = None
) -> Dict[str, Any]:
    
    # 1. Read lines first
    tasks = []
    print(f"Reading {path}...")
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            tasks.append({
                "line_str": line,
                "line_idx": i + 1, # 1-based index
                "offline": offline,
                "timeout_s": timeout_s
            })

    total_tasks = len(tasks)
    print(f"Loaded {total_tasks} tasks. Starting pool with {num_workers or 'cpu_count'} workers...")

    totals = {
        "total": 0,
        "ok": 0,
        "compile_fail": 0,
        "missing_files": 0,
        "timeout": 0,
        "tool_fail": 0,
    }
    per_sample = []

    # 2. Run in parallel
    # imap_unordered is generally faster as we don't wait for stragglers to maintain order immediately
    with multiprocessing.Pool(processes=num_workers) as pool:
        results_iter = pool.imap_unordered(process_one_line, tasks, chunksize=1)
        
        for res in tqdm(results_iter, total=total_tasks):
            totals["total"] += 1
            st = res["status"]
            if st in totals:
                totals[st] += 1
            else:
                totals["tool_fail"] += 1
            
            per_sample.append(res)

    # 3. Sort per_sample by index to match input order (optional but nice)
    per_sample.sort(key=lambda x: x["index"])

    return {"totals": totals, "per_sample": per_sample}


# ----------------------------
# 5) Extract samples with missing files
# ----------------------------
def save_missing_file_samples(
    path: str,
    *,
    output_path: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Scan a JSONL file, find samples missing Cargo.toml or main.rs,
    and write those samples (original JSONL lines) to a new file.
    """
    if output_path is None:
        output_path = path + ".missing_files.jsonl"

    totals = {
        "total": 0,
        "missing_files": 0,
        "tool_fail": 0,
    }

    with open(path, encoding="utf-8") as f_in, open(output_path, "w", encoding="utf-8") as f_out:
        for i, line in enumerate(f_in):
            if limit is not None and i >= limit:
                break

            totals["total"] += 1
            row = json.loads(line)
            llm_text = row["response"]
            if "</think>" in llm_text:
                llm_text = llm_text.split("</think>")[1]

            files = extract_cargo_and_main(llm_text)
            by_name = {x["name"] for x in files}
            if "Cargo.toml" not in by_name or "src/main.rs" not in by_name:
                totals["missing_files"] += 1
                # f_out.write(line if line.endswith("\n") else line + "\n")
                f_out.write(row["response"])
                f_out.write("\n" + "-" * 100 + "\n")

    print(totals)
    return {"totals": totals, "output_path": output_path}


def save_parsed_files_from_jsonl_line(
    line_str: str,
    *,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parse a single JSONL line (expects {"response": "..."}), extract Cargo.toml and
    src/main.rs, and write them to output_dir for manual testing.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="parsed_sample_")
        print(f"Created temporary output directory: {output_dir}")
    else:
        os.makedirs(output_dir, exist_ok=True)

    llm_text = line_str
    if "</think>" in llm_text:
        llm_text = llm_text.split("</think>")[1]

    files = extract_cargo_and_main(llm_text)
    by_name = {x["name"]: x["content"] for x in files}

    written = []
    if "Cargo.toml" in by_name:
        cargo_path = os.path.join(output_dir, "Cargo.toml")
        with open(cargo_path, "w", encoding="utf-8") as f:
            f.write(by_name["Cargo.toml"])
        written.append(cargo_path)

    if "src/main.rs" in by_name:
        src_dir = os.path.join(output_dir, "src")
        os.makedirs(src_dir, exist_ok=True)
        main_path = os.path.join(src_dir, "main.rs")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(by_name["src/main.rs"])
        written.append(main_path)

    status = "ok" if len(written) > 0 else "missing_files"
    print({
        "status": status,
        "written_files": written,
        "output_dir": output_dir,
    })


if __name__ == "__main__":
    # text = "To solve this problem, we'll use the Rayon crate for parallel processing. The approach involves:\n1. Using `par_iter()` on the outer vector to process inner vectors in parallel\n2. For each inner vector, use `par_iter().map()` to process individual elements in parallel\n3. Collect results into a new nested vector with preserved structure\n\nHere's the complete solution:\n\nCargo.toml:\n```toml\n[package]\nname = \"parallel_nested_vectors\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\nrayon = \"1.8.0\"\nrand = \"0.8.5\"\n```\n\nmain.rs:\n```rust\nuse rayon::prelude::*;\nuse rand::Rng;\n\n// Function to process each element\nfn process_element(x: &usize) -> String {\n    // Example processing: square the value and convert to string\n    let squared = x * x;\n    format!(\"{}²={}\", x, squared)\n}\n\nfn main() {\n    // Create a vector of vectors with random lengths\n    let mut rng = rand::thread_rng();\n    let a: Vec<Vec<usize>> = (0..5)\n        .map(|_| {\n            (0..rng.gen_range(2..6))\n                .map(|_| rng.gen_range(1..11))\n                .collect()\n        })\n        .collect();\n\n    println!(\"Original structure:\");\n    for (i, inner) in a.iter().enumerate() {\n        println!(\"Vector {}: {:?}\", i, inner);\n    }\n\n    // Parallel processing while preserving structure\n    let c: Vec<Vec<String>> = a\n        .par_iter()          // Process outer vec in parallel\n        .map(|inner_vec| {\n            inner_vec\n                .par_iter()  // Process inner vec in parallel\n                .map(process_element)\n                .collect()\n        })\n        .collect();\n\n    println!(\"\\nProcessed structure:\");\n    for (i, inner) in c.iter().enumerate() {\n        println!(\"Vector {}: {:?}\", i, inner);\n    }\n}\n```\n\nThis solution:\n1. Uses Rayon's parallel iterators for both outer and inner vectors\n2. Preserves the original nested structure\n3. Includes random data generation for testing\n4. Demonstrates element processing with a sample function\n5. Maintains order of elements and vectors\n\nTo test:\n1. Create new project: `cargo new parallel_vecs`\n2. Replace Cargo.toml and main.rs with above contents\n3. Run: `cargo run`\n\nSample output will show:\n- Original nested vectors with random lengths/values\n- Processed nested vectors showing squared values as strings\n- Same structure preserved with different content"
    # save_parsed_files_from_jsonl_line(text)
    path = "/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_unsure_output_20260216_143523.jsonl"
    # save_missing_file_samples(path)
    
    # Adjust num_workers based on your CPU cores. 
    # Since 'cargo check' is IO/Subprocess heavy, you can often saturation CPU count or go slightly higher.
    report = evaluate_jsonl_parallel(
        path, 
        offline=False, 
        timeout_s=360, 
        num_workers=32  # Example: set explicitly or leave None for os.cpu_count()
    )
    
    print(json.dumps(report["totals"], indent=2))

    out_path = path + ".cargo_check_report.json"
    with open(out_path, "w", encoding="utf-8") as w:
        json.dump(report, w, ensure_ascii=False, indent=2)
    print("wrote:", out_path)