import json

def check_method_hallu(path):
    response_path = path.replace(".hallucination_analysis.json", "")
    with open(response_path, "r") as f:
        line = f.readline()
        response = json.loads(line)
        model_name = response['model']
    data = json.load(open(path))
    method_hallu_num = data['summary']['hallucination_type_distribution']['method']
    import_hallu_num = data['summary']['hallucination_type_distribution']['import']
    feature_hallu_num = data['summary']['hallucination_type_distribution']['feature']
    any_hallu_num = data['summary']['samples_with_hallucinations']
    total_num = data['summary']['total_samples']
    import_ratio = import_hallu_num / total_num
    feature_ratio = feature_hallu_num / total_num
    any_ratio = any_hallu_num / total_num
    ratio = method_hallu_num / total_num
    print(f"{model_name:<30}: method: {method_hallu_num:<3}/{total_num:<5} ({ratio:<7.2%}) import: {import_hallu_num:<3}/{total_num:<5} ({import_ratio:<7.2%}) feature: {feature_hallu_num:<3}/{total_num:<5} ({feature_ratio:<7.2%}) any: {any_hallu_num:<3}/{total_num:<5} ({any_ratio:<7.2%})")

paths = """/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260206_161129.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260206_165400.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260206_171431.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260206_195439.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260208_153333.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260208_172946.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260210_113118.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260211_134843.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260211_140206.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260211_161247.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260216_121021.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260216_131641.jsonl.hallucination_analysis.json
/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_unsure_output_20260216_143523.jsonl.hallucination_analysis.json"""

paths = paths.split("\n")
for path in paths:
    check_method_hallu(path)