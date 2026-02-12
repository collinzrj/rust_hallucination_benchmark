import json
import re
from typing import Dict, List, Any, Set, Optional
from collections import defaultdict, Counter


def extract_method_name_from_error(message: str, rendered: str) -> Optional[str]:
    """Extract method/function name from error message."""
    # Pattern: "no method named `X` found"
    match = re.search(r"no method named `([^`]+)` found", message)
    if match:
        return match.group(1)
    
    # Pattern: "no function named `X` found"
    match = re.search(r"no function named `([^`]+)` found", message)
    if match:
        return match.group(1)
    
    # Pattern: "method `X` exists" (but trait bounds not satisfied)
    match = re.search(r"the method `([^`]+)` exists", message)
    if match:
        return match.group(1)
    
    return None


def extract_type_name_from_error(message: str) -> Optional[str]:
    """Extract type name from error message."""
    # Pattern: "use of undeclared type `X`"
    match = re.search(r"use of undeclared type `([^`]+)`", message)
    if match:
        return match.group(1)
    
    # Pattern: "failed to resolve: use of unresolved module or unlinked crate `X`"
    match = re.search(r"use of unresolved module or unlinked crate `([^`]+)`", message)
    if match:
        return match.group(1)
    
    # Pattern: "unresolved import `X`"
    match = re.search(r"unresolved import `([^`]+)`", message)
    if match:
        return match.group(1)
    
    return None


def extract_crate_name_from_error(message: str) -> Optional[str]:
    """Extract crate name from error message."""
    # Pattern: "failed to resolve: use of unresolved module or unlinked crate `X`"
    match = re.search(r"use of unresolved module or unlinked crate `([^`]+)`", message)
    if match:
        return match.group(1)
    
    # Pattern: "unresolved import `X::Y`" - extract the crate/module part
    match = re.search(r"unresolved import `([^:]+)", message)
    if match:
        return match.group(1)
    
    return None


def extract_feature_name_from_error(message: str) -> Optional[str]:
    """Extract feature name from cargo build failure."""
    # Pattern: "depends on `X` with feature `Y` but `X` does not have that feature"
    match = re.search(r"depends on `[^`]+` with feature `([^`]+)` but", message)
    if match:
        return match.group(1)
    
    return None


def extract_trait_bound_info(message: str) -> Optional[Dict[str, str]]:
    """Extract trait bound information from error."""
    # Pattern: "the trait bound `X: Y` is not satisfied"
    match = re.search(r"the trait bound `([^:]+):\s*([^`]+)` is not satisfied", message)
    if match:
        return {"type": match.group(1), "trait": match.group(2)}
    
    return None


def detect_wrong_signature(message: str) -> Optional[Dict[str, Any]]:
    """Detect wrong function/method signature (argument count mismatch)."""
    # Pattern: "this function takes X argument(s) but Y argument(s) were supplied"
    match = re.search(
        r"this function takes (\d+) argument(?:s)? but (\d+) argument(?:s)? were supplied",
        message
    )
    if match:
        return {
            "expected": int(match.group(1)),
            "supplied": int(match.group(2)),
            "type": "function"
        }
    
    # Pattern: "method takes X argument(s) but Y argument(s) were supplied"
    match = re.search(
        r"method takes (\d+) argument(?:s)? but (\d+) argument(?:s)? were supplied",
        message
    )
    if match:
        return {
            "expected": int(match.group(1)),
            "supplied": int(match.group(2)),
            "type": "method"
        }
    
    return None


def is_hallucinated_import_error(error: Dict[str, Any]) -> bool:
    """Check if error indicates a hallucinated import."""
    message = error.get("message", "").lower()
    code = error.get("code", "")
    
    patterns = [
        "unresolved import",
        "use of unresolved module",
        "unlinked crate",
        "cannot find",
        "use of undeclared type",
        "failed to resolve",
    ]
    
    return any(pattern in message for pattern in patterns)


def is_hallucinated_method_error(error: Dict[str, Any]) -> bool:
    """Check if error indicates a hallucinated method/function."""
    message = error.get("rendered", "").lower()
    code = error.get("code", "")
    
    # Not hallucinated: method provided by a trait that's not in scope.
    if "items from traits can only be used if the trait is in scope" in message:
        return False
    if "but its trait bounds were not satisfied" in message:
        return False
    if "trait" in message and "provides" in message and "implemented but not in scope" in message:
        return False

    # E0599 is "no method named X found"
    if code == "E0599":
        return True
    
    patterns = [
        "no method named",
        "no function named",
        "method not found",
        "function not found",
    ]
    
    return any(pattern in message for pattern in patterns)


def is_method_trait_bound_error(error: Dict[str, Any]) -> bool:
    """Check if error indicates method exists but trait bounds not satisfied (wrong API usage)."""
    message = error.get("message", "")
    
    # Pattern: "the method `X` exists for struct `Y`, but its trait bounds were not satisfied"
    if "the method" in message and "exists" in message and "trait bounds were not satisfied" in message:
        return True
    
    return False


def is_hallucinated_feature_error(error: Dict[str, Any]) -> bool:
    """Check if error indicates a hallucinated feature."""
    message = error.get("message", "")
    code = error.get("code", "")
    
    if code == "cargo-build-failure":
        if "does not have that feature" in message:
            return True
    
    return False


def is_wrong_signature_error(error: Dict[str, Any]) -> bool:
    """Check if error indicates wrong method/function signature."""
    message = error.get("message", "")
    code = error.get("code", "")
    
    # E0061 is "this function takes X arguments but Y arguments were supplied"
    if code == "E0061":
        return True
    
    return "takes" in message.lower() and "argument" in message.lower() and "supplied" in message.lower()


def analyze_sample(sample: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single sample for hallucination indicators."""
    status = sample.get("status", "")
    errors = sample.get("errors", [])
    
    result = {
        "index": sample.get("index"),
        "status": status,
        "has_hallucination": False,
        "hallucination_types": [],
        "hallucination_errors": [],
        "hallucinated_items": {
            "methods": [],
            "types": [],
            "crates": [],
            "features": [],
            "traits": [],
        },
        "wrong_signatures": [],
        "error_codes": [],
    }
    
    if status != "compile_fail":
        return result
    
    for error in errors:
        message = error.get("message", "")
        code = error.get("code", "")
        rendered = error.get("rendered", "")
        
        result["error_codes"].append(code)
        hallucination_triggered = False
        
        # Check for hallucinated imports
        if is_hallucinated_import_error(error):
            result["has_hallucination"] = True
            hallucination_triggered = True
            if "import" not in result["hallucination_types"]:
                result["hallucination_types"].append("import")
            
            type_name = extract_type_name_from_error(message)
            if type_name:
                result["hallucinated_items"]["types"].append(type_name)
            
            crate_name = extract_crate_name_from_error(message)
            if crate_name:
                result["hallucinated_items"]["crates"].append(crate_name)
        
        # Check for hallucinated methods
        if is_hallucinated_method_error(error):
            result["has_hallucination"] = True
            hallucination_triggered = True
            if "method" not in result["hallucination_types"]:
                result["hallucination_types"].append("method")
            
            method_name = extract_method_name_from_error(message, rendered)
            if method_name:
                result["hallucinated_items"]["methods"].append(method_name)
        
        # # Check for method with wrong trait bounds (method exists but can't be used)
        # if is_method_trait_bound_error(error):
        #     result["has_hallucination"] = True
        #     if "method_trait_bound" not in result["hallucination_types"]:
        #         result["hallucination_types"].append("method_trait_bound")
            
        #     method_name = extract_method_name_from_error(message, rendered)
        #     if method_name:
        #         result["hallucinated_items"]["methods"].append(method_name)
        
        # Check for hallucinated features
        if is_hallucinated_feature_error(error):
            result["has_hallucination"] = True
            hallucination_triggered = True
            if "feature" not in result["hallucination_types"]:
                result["hallucination_types"].append("feature")
            
            feature_name = extract_feature_name_from_error(message)
            if feature_name:
                result["hallucinated_items"]["features"].append(feature_name)
        
        # # Check for wrong signatures
        # if is_wrong_signature_error(error):
        #     result["has_hallucination"] = True
        #     if "signature" not in result["hallucination_types"]:
        #         result["hallucination_types"].append("signature")
            
        #     sig_info = detect_wrong_signature(message)
        #     if sig_info:
        #         result["wrong_signatures"].append(sig_info)
        
        # # Check for trait bound issues (might indicate hallucinated trait or wrong API usage)
        # trait_info = extract_trait_bound_info(message)
        # if trait_info:
        #     # Only mark as hallucination if it's a clear trait bound issue
        #     # (not all trait bound errors are hallucinations, but many indicate wrong API assumptions)
        #     if "trait_bound" not in result["hallucination_types"]:
        #         result["hallucination_types"].append("trait_bound")
        #     result["hallucinated_items"]["traits"].append(trait_info)

        if hallucination_triggered:
            code_line = None
            spans = error.get("spans") or []
            if spans:
                text_entries = spans[0].get("text") or []
                if text_entries:
                    code_line = text_entries[0].get("text")
            result["hallucination_errors"].append({
                "code": code,
                "message": message,
                "code_line": code_line,
                "msg_hallucination_types": list(result["hallucination_types"]),  # explicit copy so mutation doesn't affect history
            })
    
    return result


def analyze_report(report_path: str) -> Dict[str, Any]:
    """Analyze the entire cargo check report."""
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    
    totals = report.get("totals", {})
    per_sample = report.get("per_sample", [])
    
    # Analyze each sample
    analyzed_samples = []
    hallucination_stats = {
        "total_samples": len(per_sample),
        "samples_with_hallucinations": 0,
        "hallucination_type_counts": Counter(),
        "hallucinated_methods": Counter(),
        "hallucinated_types": Counter(),
        "hallucinated_crates": Counter(),
        "hallucinated_features": Counter(),
        "wrong_signature_count": 0,
        "error_code_counts": Counter(),
    }
    
    for sample in per_sample:
        analysis = analyze_sample(sample)
        analyzed_samples.append(analysis)
        
        if analysis["has_hallucination"]:
            hallucination_stats["samples_with_hallucinations"] += 1
            
            for h_type in analysis["hallucination_types"]:
                hallucination_stats["hallucination_type_counts"][h_type] += 1
            
            for method in analysis["hallucinated_items"]["methods"]:
                hallucination_stats["hallucinated_methods"][method] += 1
            
            for type_name in analysis["hallucinated_items"]["types"]:
                hallucination_stats["hallucinated_types"][type_name] += 1
            
            for crate_name in analysis["hallucinated_items"]["crates"]:
                hallucination_stats["hallucinated_crates"][crate_name] += 1
            
            for feature_name in analysis["hallucinated_items"]["features"]:
                hallucination_stats["hallucinated_features"][feature_name] += 1
            
            if analysis["wrong_signatures"]:
                hallucination_stats["wrong_signature_count"] += len(analysis["wrong_signatures"])
        
        for code in analysis["error_codes"]:
            hallucination_stats["error_code_counts"][code] += 1
    
    return {
        "summary": {
            "total_samples": hallucination_stats["total_samples"],
            "compile_fail_samples": totals.get("compile_fail", 0),
            "samples_with_hallucinations": hallucination_stats["samples_with_hallucinations"],
            "hallucination_rate": (
                hallucination_stats["samples_with_hallucinations"] / hallucination_stats["total_samples"]
                if hallucination_stats["total_samples"] > 0 else 0
            ),
            "hallucination_type_distribution": dict(hallucination_stats["hallucination_type_counts"]),
            "top_hallucinated_methods": dict(hallucination_stats["hallucinated_methods"].most_common(20)),
            "top_hallucinated_types": dict(hallucination_stats["hallucinated_types"].most_common(20)),
            "top_hallucinated_crates": dict(hallucination_stats["hallucinated_crates"].most_common(20)),
            "top_hallucinated_features": dict(hallucination_stats["hallucinated_features"].most_common(20)),
            "wrong_signature_count": hallucination_stats["wrong_signature_count"],
            "top_error_codes": dict(hallucination_stats["error_code_counts"].most_common(20)),
        },
        "per_sample_analysis": analyzed_samples,
    }


def print_summary(analysis: Dict[str, Any]):
    """Print a human-readable summary of the analysis."""
    summary = analysis["summary"]
    
    print("=" * 80)
    print("HALLUCINATION ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    
    print(f"Total samples: {summary['total_samples']}")
    print(f"Compile failures: {summary['compile_fail_samples']}")
    print(f"Samples with hallucinations: {summary['samples_with_hallucinations']}")
    print(f"Hallucination rate: {summary['hallucination_rate']:.2%}")
    print()
    
    print("Hallucination Type Distribution:")
    for h_type, count in sorted(summary["hallucination_type_distribution"].items(), key=lambda x: -x[1]):
        print(f"  {h_type}: {count}")
    print()
    
    if summary["top_hallucinated_methods"]:
        print("Top Hallucinated Methods:")
        for method, count in list(summary["top_hallucinated_methods"].items())[:10]:
            print(f"  {method}: {count}")
        print()
    
    if summary["top_hallucinated_types"]:
        print("Top Hallucinated Types:")
        for type_name, count in list(summary["top_hallucinated_types"].items())[:10]:
            print(f"  {type_name}: {count}")
        print()
    
    if summary["top_hallucinated_crates"]:
        print("Top Hallucinated Crates:")
        for crate, count in list(summary["top_hallucinated_crates"].items())[:10]:
            print(f"  {crate}: {count}")
        print()
    
    if summary["top_hallucinated_features"]:
        print("Top Hallucinated Features:")
        for feature, count in list(summary["top_hallucinated_features"].items())[:10]:
            print(f"  {feature}: {count}")
        print()
    
    if summary["wrong_signature_count"] > 0:
        print(f"Wrong signature errors: {summary['wrong_signature_count']}")
        print()
    
    print("Top Error Codes:")
    for code, count in list(summary["top_error_codes"].items())[:10]:
        print(f"  {code}: {count}")
    print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        report_path = "/share/shmatikov/collin/code_hallucination/data/rust_hallucination_questions_output_20260206_195439.jsonl.cargo_check_report.json"
    else:
        report_path = sys.argv[1]
    
    print(f"Analyzing report: {report_path}")
    analysis = analyze_report(report_path)
    
    print_summary(analysis)
    
    # Write detailed analysis to file
    output_path = report_path.replace(".cargo_check_report.json", ".hallucination_analysis.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    print(f"\nDetailed analysis written to: {output_path}")

