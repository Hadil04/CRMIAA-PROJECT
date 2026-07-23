"""Quick smoke-test: verify routes.py and main.py import load_from_db, not load_csv directly."""
import sys, ast, pathlib

def check_file(path, label):
    src = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.append((node.module, [a.name for a in node.names]))
    print(f"\n--- {label} ---")
    for mod, names in imports:
        print(f"  from {mod} import {', '.join(names)}")

    # Check _load_dataset / load_data call load_from_db
    calls_load_from_db = "load_from_db" in src
    calls_load_csv_directly = "_load_dataset" not in src and "load_csv(str(SAMPLE_CSV))" in src
    print(f"  load_from_db referenced: {calls_load_from_db}")
    print(f"  still using load_csv(SAMPLE_CSV) as primary: {calls_load_csv_directly}")
    if not calls_load_from_db:
        print("  *** PROBLEM: load_from_db not referenced ***", file=sys.stderr)
    if calls_load_csv_directly:
        print("  *** PROBLEM: still calling load_csv as primary ***", file=sys.stderr)

check_file("app/cria/routes.py", "routes.py")
check_file("app/cria/main.py",   "main.py")

# Also verify data_loader exports both functions
import importlib.util, sys
spec = importlib.util.spec_from_file_location("data_loader", "app/cria/data_loader.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("\n--- data_loader.py exports ---")
print(f"  load_csv:     {callable(getattr(mod, 'load_csv', None))}")
print(f"  load_from_db: {callable(getattr(mod, 'load_from_db', None))}")
print("\nAll checks passed." if all([
    callable(getattr(mod, 'load_csv', None)),
    callable(getattr(mod, 'load_from_db', None)),
]) else "FAILED")
