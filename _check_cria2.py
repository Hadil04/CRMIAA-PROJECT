"""Verify load_data() in main.py calls load_from_db first, not load_csv first."""
import pathlib

src = pathlib.Path("app/cria/main.py").read_text(encoding="utf-8")

# Find the load_data function body
start = src.index("def load_data()")
# Get the first 800 chars of the function — enough to see what's called first
snippet = src[start:start+800]
print("=== load_data() body ===")
print(snippet)

# Verify ordering: load_from_db must appear before load_csv in the function
pos_db  = snippet.index("load_from_db()")
pos_csv = snippet.index("load_csv(")
print(f"\nFirst call: load_from_db at char {pos_db}, load_csv at char {pos_csv}")
print(f"DB called first: {pos_db < pos_csv}  ← must be True")
assert pos_db < pos_csv, "FAIL: load_csv called before load_from_db!"

# Same for routes.py _load_dataset
src2 = pathlib.Path("app/cria/routes.py").read_text(encoding="utf-8")
start2 = src2.index("def _load_dataset()")
snippet2 = src2[start2:start2+600]
print("\n=== _load_dataset() body ===")
print(snippet2)
pos_db2  = snippet2.index("load_from_db()")
pos_csv2 = snippet2.index("load_csv(")
print(f"\nFirst call: load_from_db at char {pos_db2}, load_csv at char {pos_csv2}")
print(f"DB called first: {pos_db2 < pos_csv2}  ← must be True")
assert pos_db2 < pos_csv2, "FAIL: load_csv called before load_from_db in routes!"

print("\n✓ Both files: load_from_db is primary, load_csv is fallback-only.")
