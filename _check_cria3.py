import pathlib

# ---- main.py: load_data() ----
src = pathlib.Path("app/cria/main.py").read_text(encoding="utf-8")
start = src.index("def load_data()")
end   = src.index("\ndef print_menu()")
body  = src[start:end]

db_pos  = body.index("load_from_db()")
csv_pos = body.index("load_csv(")
print(f"main.py  load_data:      load_from_db @ {db_pos:3d}, load_csv @ {csv_pos:3d}  → DB first: {db_pos < csv_pos}")

# ---- routes.py: _load_dataset() ----
src2   = pathlib.Path("app/cria/routes.py").read_text(encoding="utf-8")
start2 = src2.index("def _load_dataset()")
end2   = src2.index("\ndef _render_index(")
body2  = src2[start2:end2]

db_pos2  = body2.index("load_from_db()")
csv_pos2 = body2.index("load_csv(")
print(f"routes.py _load_dataset: load_from_db @ {db_pos2:3d}, load_csv @ {csv_pos2:3d}  → DB first: {db_pos2 < csv_pos2}")

assert db_pos  < csv_pos,  "FAIL main.py"
assert db_pos2 < csv_pos2, "FAIL routes.py"
print("\nAll assertions passed — both files call load_from_db() before load_csv().")
