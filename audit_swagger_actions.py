import ast
import os

CODEBASE_PATH = "apps"  # set to the root where your ViewSets live (adjust if needed)


class ActionAuditVisitor(ast.NodeVisitor):
    def __init__(self):
        self.results = []

    def visit_ClassDef(self, node):
        class_name = node.name
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_name = item.name
                has_action = False
                has_swagger = False
                swagger_has_body = False

                for deco in item.decorator_list:
                    # Check for @action decorator
                    if (
                        isinstance(deco, ast.Call)
                        and getattr(deco.func, "id", "") == "action"
                    ):
                        has_action = True

                    # Check for @swagger_auto_schema decorator
                    if (
                        isinstance(deco, ast.Call)
                        and getattr(deco.func, "id", "") == "swagger_auto_schema"
                    ):
                        has_swagger = True
                        # Look for request_body argument
                        for kw in deco.keywords:
                            if kw.arg == "request_body":
                                swagger_has_body = True

                if has_action:
                    self.results.append(
                        {
                            "class": class_name,
                            "method": method_name,
                            "has_swagger": has_swagger,
                            "swagger_has_body": swagger_has_body,
                            "lineno": item.lineno,
                        }
                    )
        # Continue to scan subclasses
        self.generic_visit(node)


def audit_actions(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=file_path)
    visitor = ActionAuditVisitor()
    visitor.visit(tree)
    return visitor.results


def scan_codebase(root_dir):
    for dirpath, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(dirpath, file)
                try:
                    results = audit_actions(full_path)
                    for res in results:
                        if not (res["has_swagger"] and res["swagger_has_body"]):
                            print(
                                f"❌ {full_path}:{res['lineno']} "
                                f"{res['class']}.{res['method']}() missing @swagger_auto_schema(request_body=...)"
                            )
                        else:
                            print(
                                f"✅ {full_path}:{res['lineno']} "
                                f"{res['class']}.{res['method']}() has @swagger_auto_schema(request_body=...)"
                            )
                except Exception as e:
                    print(f"[WARN] Skipped {full_path}: {e}")


if __name__ == "__main__":
    scan_codebase(CODEBASE_PATH)
