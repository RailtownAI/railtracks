import sys

from tomlkit import parse

with open("pyproject.toml", "r") as f:
    doc = parse(f.read())

try:
    dependencies = doc["project"]["dependencies"]
except KeyError:
    print("[project] dependencies not found in pyproject.toml")
    sys.exit(1)

sorted_deps = sorted(dependencies, key=lambda s: s.lower())
if list(dependencies) != sorted_deps:
    print("[project] dependencies are not sorted alphabetically:")
    for dep in dependencies:
        print(f"  {dep}")
    print("\nExpected order:")
    for dep in sorted_deps:
        print(f"  {dep}")
    sys.exit(1)
else:
    print("[project] dependencies are sorted alphabetically.")
