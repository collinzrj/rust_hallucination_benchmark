import json


def collect_method_hallu(path):
    response_path = path.replace(".hallucination_analysis.json", "")
    cargo_check_path = response_path + ".cargo_check_report.json"

    with open(cargo_check_path, "r") as f:
        ok_num = json.load(f)["totals"]["ok"]

    with open(response_path, "r") as f:
        line = f.readline()
        response = json.loads(line)
        model_name = response["model"]

    with open(path, "r") as f:
        data = json.load(f)

    method_hallu_num = data["summary"]["hallucination_type_distribution"]["method"]
    import_hallu_num = data["summary"]["hallucination_type_distribution"]["import"]
    feature_hallu_num = data["summary"]["hallucination_type_distribution"]["feature"]
    any_hallu_num = data["summary"]["samples_with_hallucinations"]
    total_num = data["summary"]["total_samples"]

    return {
        "model": model_name,
        "method": method_hallu_num,
        "import": import_hallu_num,
        "feature": feature_hallu_num,
        "any": any_hallu_num,
        "ok": ok_num,
        "total": total_num,
    }


def ratio_str(count, total):
    return f"{(count / total):.2%}"


def to_markdown(rows):
    lines = [
        "# Hallucination Comparison",
        "",
        "| Model | Method Hallucination | Import Hallucination | Feature Hallucination | Any Hallucination | Pass Compilation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        total = row["total"]
        lines.append(
            f"| {row['model']} | "
            f"{row['method']} ({ratio_str(row['method'], total)}) | "
            f"{row['import']} ({ratio_str(row['import'], total)}) | "
            f"{row['feature']} ({ratio_str(row['feature'], total)}) | "
            f"{row['any']} ({ratio_str(row['any'], total)}) |"
            f"{row['ok']} ({ratio_str(row['ok'], total)}) |"
        )

    lines.append("")
    return "\n".join(lines)

paths = """/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260208_172946.openai_gpt-5.2.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260210_113118.qwen3-max-2026-01-23.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260211_134843.anthropic_claude-opus-4.6.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260211_140206.z-ai_glm-5.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260211_161247.deepseek_deepseek-r1.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260216_121021.qwen_qwen3.5-plus-02-15.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260228_161647.gemini-3.1-pro-preview.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260228_173820.kimi-k2.5.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260228_181823.minimax-m2.5.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260228_213412.qwen3.5-27b.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260228_215031.deepseek-v3.2.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260228_215635_qwen3-coder-next.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260228_221518_qwen3.5-35b-a3b.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260228_232801_gpt-5.3-codex.jsonl.hallucination_analysis.json"""

def main():
    path_list = [p for p in paths.split("\n") if p.strip()]
    rows = [collect_method_hallu(path) for path in path_list]
    rows.sort(key=lambda row: row["any"])

    markdown = to_markdown(rows)
    print(markdown)


if __name__ == "__main__":
    main()