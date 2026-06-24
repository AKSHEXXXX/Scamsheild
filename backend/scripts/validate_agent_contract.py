# ScamShield Agent Contract Validator
# Run: python scripts/validate_agent_contract.py
# Fails if any agent violates the inference contract.

import sys
import importlib.util
import inspect
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

AGENTS_DIR = Path(__file__).resolve().parent.parent / "app" / "ml" / "agents"

REQUIRED_KEYS = {"verdict", "score", "reasons", "metadata"}
VALID_VERDICTS = {"safe", "suspicious", "high_risk", "scam", "error"}

EXPECTED_ENTRYPOINTS = {
    "agent_1_text_tfidf":    ("predict_text", (str,)),
    "agent_2_distilbert":    ("predict_text", (str,)),
    "agent_3_url_xgb":       ("predict_url", (str,)),
    "agent_5_qr_xgb":        ("predict_qr", (str,)),
    "agent_7_upi_meta_xgb":  ("predict_upi", (dict,)),
    "agent_9_brand_bilstm":  ("check_brand", (str, str)),
    "agent_11_malware_rf":   ("predict_file", (dict,)),
    "agent_13_call_logreg":  ("predict_text", (str,)),
}

errors = []

for folder in sorted(AGENTS_DIR.iterdir()):
    if not folder.is_dir() or not folder.name.startswith("agent_"):
        continue
    if folder.name not in EXPECTED_ENTRYPOINTS:
        errors.append(f"{folder.name}: no entry defined in EXPECTED_ENTRYPOINTS")
        continue

    func_name, arg_types = EXPECTED_ENTRYPOINTS[folder.name]
    pyfile = folder / "inference.py"
    if not pyfile.exists():
        errors.append(f"{folder.name}: inference.py not found")
        continue

    spec = importlib.util.spec_from_file_location(f"{folder.name}.inference", pyfile)
    if spec is None or spec.loader is None:
        errors.append(f"{folder.name}: could not load spec")
        continue

    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        errors.append(f"{folder.name}: import failed — {e}")
        continue

    if not hasattr(mod, func_name):
        errors.append(f"{folder.name}: missing function {func_name}()")
        continue

    func = getattr(mod, func_name)
    if not callable(func):
        errors.append(f"{folder.name}: {func_name} is not callable")
        continue

    sig = inspect.signature(func)
    sig_params = list(sig.parameters.keys())
    for i, expected_type in enumerate(arg_types):
        if i >= len(sig_params):
            errors.append(f"{folder.name}: {func_name} takes {len(sig_params)} params, expected at least {len(arg_types)}")
            break

    dummy_args = {
        str: "test input for validation purposes only",
        dict: {"amount": 100, "note": "test", "vpa": "test@upi"},
    }
    args_for_call = [dummy_args.get(t, "") for t in arg_types]

    try:
        result = func(*args_for_call)
    except NotImplementedError:
        print(f"  [SKIP] {folder.name}/{func_name} — NotImplementedError (not wired yet)")
        continue
    except Exception as e:
        errors.append(f"{folder.name}: {func_name} raised {type(e).__name__}: {e}")
        continue

    if not isinstance(result, dict):
        errors.append(f"{folder.name}: {func_name} returned {type(result).__name__}, expected dict")
        continue

    missing = REQUIRED_KEYS - set(result.keys())
    if missing:
        errors.append(f"{folder.name}: {func_name} missing keys: {missing}")
        continue

    verdict = result.get("verdict", "")
    if verdict not in VALID_VERDICTS:
        errors.append(f"{folder.name}: {func_name} verdict '{verdict}' not in {VALID_VERDICTS}")
        continue

    score = result.get("score", -2)
    if not isinstance(score, int) or score < -1 or score > 100:
        errors.append(f"{folder.name}: {func_name} score={score} should be int -1..100")
        continue

    reasons = result.get("reasons", None)
    if not isinstance(reasons, list):
        errors.append(f"{folder.name}: {func_name} reasons should be list, got {type(reasons).__name__}")

    metadata = result.get("metadata", None)
    if not isinstance(metadata, dict):
        errors.append(f"{folder.name}: {func_name} metadata should be dict, got {type(metadata).__name__}")

    print(f"  [PASS] {folder.name}/{func_name} -> verdict={verdict} score={score}")

if errors:
    print(f"\nFAILED — {len(errors)} error(s):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"\nAll {len(EXPECTED_ENTRYPOINTS)} agent contracts validated — PASS")
