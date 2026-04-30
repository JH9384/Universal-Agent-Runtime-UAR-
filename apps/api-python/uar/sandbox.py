import ast
ALLOWED = (ast.Expression, ast.Call, ast.Name, ast.Load, ast.Constant)

def validate(code):
    tree = ast.parse(code, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED):
            raise ValueError("disallowed")
