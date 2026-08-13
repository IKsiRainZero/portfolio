"""Dead code and dependency audit for Crescent."""
import ast, os, re
from collections import defaultdict

ROOT = "Crescent"
SKIP_DIRS = {"__pycache__", ".pytest_cache", "dist", "build", "docs", "templates", "static", "data", "image"}


def all_py_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f).replace(os.sep, "/")


# ── 1. Route registration in main.py ──
print("=" * 60)
print("1. ROUTE REGISTRATION IN main.py")
print("=" * 60)
with open(f"{ROOT}/main.py", encoding="utf-8") as f:
    main_lines = f.readlines()

imported_routes = []
registered_routers = []
for line in main_lines:
    s = line.strip()
    if "from routes" in s or "import routes" in s:
        imported_routes.append(s)
    if "include_router" in s:
        registered_routers.append(s)

print("Imported route modules:")
for r in imported_routes:
    print(f"  {r}")
print("\nRegistered routers:")
for r in registered_routers:
    print(f"  {r}")

# ── 2. Template references ──
print(f"\n{'=' * 60}")
print("2. TEMPLATES REFERENCED BY ACTIVE ROUTES")
print("=" * 60)
active_templates = set()
unused_templates = set()

existing_templates = set()
for dirpath, _, filenames in os.walk(f"{ROOT}/templates"):
    for f in filenames:
        if f.endswith(".html"):
            existing_templates.add(f)

for fpath in all_py_files():
    if "/routes/" not in fpath:
        continue
    try:
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        continue
    # Find template references in Jinja2 style
    for m in re.finditer(r"['\"]([^'\"]+\.html)['\"]", content):
        tpl = m.group(1)
        # Normalize: strip pages/ prefix if present
        fname = os.path.basename(tpl)
        active_templates.add(fname)

for t in sorted(existing_templates):
    if t not in active_templates:
        unused_templates.add(t)

print("Unused templates (no route references them):")
for t in sorted(unused_templates):
    print(f"  templates/*/{t}" if t else "  (none)")
print(f"\nActive: {len(active_templates)}, Unused: {len(unused_templates)}")

# ── 3. v3 → v4 overlap ──
print(f"\n{'=' * 60}")
print("3. WHO IMPORTS v3 SERVICES?")
print("=" * 60)
v3_targets = ["knowledge_ingest", "credibility_gate", "source_tracer"]
for fpath in sorted(all_py_files()):
    if "/tests/" in fpath:
        continue
    try:
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        continue
    for target in v3_targets:
        pattern = re.compile(rf"(from\s+\S*{target}\s+import|import\s+\S*{target})")
        if pattern.search(content):
            short = fpath.replace("Crescent/", "")
            print(f"  {short} → {target}")

# ── 4. Dead code: services with zero incoming refs from non-test code ──
print(f"\n{'=' * 60}")
print("4. SERVICES WITH NO IMPORTERS (excluding tests)")
print("=" * 60)

# Build: module basename → filepath
all_mods = {}
for fpath in all_py_files():
    mod = os.path.basename(fpath).replace(".py", "")
    all_mods[mod] = fpath

# Track which service files are imported by non-test code
imported_mods = set()
for fpath in all_py_files():
    if "/tests/" in fpath:
        continue
    try:
        with open(fpath, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                parts = node.module.split(".")
                imported_mods.add(parts[-1])
                imported_mods.add(parts[0])  # top-level package
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_mods.add(alias.name.split(".")[0])

service_files = {f for f in all_py_files() if "/services/" in f and not f.endswith("__init__.py")}
dead_services = set()
for fpath in sorted(service_files):
    mod = os.path.basename(fpath).replace(".py", "")
    if mod not in imported_mods and fpath not in imported_mods:
        dead_services.add(fpath)

if dead_services:
    for fpath in sorted(dead_services):
        short = fpath.replace("Crescent/services/", "")
        size = os.path.getsize(fpath)
        print(f"  {short} ({size} bytes)")
else:
    print("  (none — all services are imported somewhere)")

# ── 5. Summary stats ──
print(f"\n{'=' * 60}")
print("5. FILE COUNTS")
print("=" * 60)
dirs = defaultdict(int)
for fpath in all_py_files():
    d = os.path.dirname(fpath).replace("Crescent/", "")
    if d == "":
        d = "(root)"
    dirs[d] += 1
for d, c in sorted(dirs.items()):
    print(f"  {d}: {c} files")
