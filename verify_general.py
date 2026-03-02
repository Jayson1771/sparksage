import os

path = "cogs/general.py"

print("=== FILE EXISTS ===")
print(os.path.exists(path))

print("\n=== FILE SIZE ===")
print(os.path.getsize(path), "bytes")

print("\n=== HAS DEBUG PRINT ===")
with open(path, "rb") as f:
    content = f.read().decode("utf-8", errors="replace")
print("has ANALYTICS DEBUG:", "ANALYTICS DEBUG" in content)
print("has cost_calculator:", "cost_calculator" in content)
print("has estimate_cost:", "estimate_cost_from_text" in content)

print("\n=== FIRST 10 LINES ===")
for i, line in enumerate(content.splitlines()[:10]):
    print(f"{i+1}: {line}")