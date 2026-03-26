import ast
import hashlib
import sys
from pathlib import Path


def normalize_node(node: ast.AST) -> str:
    """
    Convert an AST node into a normalized string representation.
    """
    return ast.dump(node, annotate_fields=False, include_attributes=False)


def function_hash(func: ast.FunctionDef, *, consider_name=False) -> str:
    """
    Generate a stable hash for a function definition.
    By default, function names are ignored.
    """
    data = {
        "args": normalize_node(func.args),
        "body": [normalize_node(stmt) for stmt in func.body],
    }

    if consider_name:
        data["name"] = func.name

    raw = repr(data).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class DuplicateFunctionRemover(ast.NodeTransformer):
    def __init__(self, consider_name=False):
        self.consider_name = consider_name
        self.seen_hashes: dict[str, str] = {}
        self.removed = []

    def visit_FunctionDef(self, node):
        h = function_hash(node, consider_name=self.consider_name)

        if h in self.seen_hashes:
            self.removed.append((node.name, self.seen_hashes[h]))
            return None  # remove this function

        self.seen_hashes[h] = node.name
        return node


def remove_duplicates(source: str, *, consider_name=False) -> tuple[str, list]:
    tree = ast.parse(source)

    remover = DuplicateFunctionRemover(consider_name)
    tree = remover.visit(tree)
    ast.fix_missing_locations(tree)

    new_source = ast.unparse(tree)
    return new_source, remover.removed


def main(path: Path, *, in_place=False, consider_name=False):
    source = path.read_text(encoding="utf-8")
    new_source, removed = remove_duplicates(
        source, consider_name=consider_name
    )

    if removed:
        print(f"Removed {len(removed)} duplicate function(s):")
        for dup, original in removed:
            print(f"  {dup} (duplicate of {original})")
    else:
        print("No duplicate functions found.")

    if in_place:
        path.write_text(new_source, encoding="utf-8")
    else:
        print("\n--- Cleaned source ---\n")
        print(new_source)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python remove_duplicate_functions.py <file.py> [--in-place]")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    in_place = "--in-place" in sys.argv

    main(
        file_path,
        in_place=in_place,
        consider_name=False,  # set True if name must also match
    )