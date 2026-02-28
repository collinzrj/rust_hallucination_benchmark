import json_repair
import sys
path = '/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260211_134843.jsonl'

with open(path, 'r') as f:
    lines = f.readlines()
    pattern = sys.argv[1]
    for line in lines:
        if pattern in line:
            data = json_repair.loads(line)
            response = json_repair.loads(data['response'])
            if type(response) is not dict:
                response = response[0]
            try:
                print("Cargo.toml:")
                print(response['Cargo.toml'])
                print("-" * 100)
                print("main.rs:")
                print(response['main.rs'])
            except:
                print("Error parsing response")
                print(response)
            print("-" * 100)
            print(data['response'])
            break