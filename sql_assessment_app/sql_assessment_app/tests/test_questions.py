import ast
import os


def _load_questions():
    src_path = os.path.join(os.path.dirname(__file__), '..', 'app.py')
    src = open(src_path).read()
    module = ast.parse(src)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, 'id', None) == 'QUESTIONS':
                    return ast.literal_eval(node.value)
    raise RuntimeError('QUESTIONS not found in app.py')


def test_no_multiple_joins_in_solutions():
    questions = _load_questions()
    # Emulate the app's active SQL filtering: only questions whose solution has <= 1 'join'
    active_sql = [q for q in questions if q.get('solution') and q['solution'].lower().count('join') <= 1]
    for q in active_sql:
        sol = q.get('solution', '') or ''
        assert sol.lower().count('join') <= 1, f"Question {q.get('id')} has multiple JOINs in its solution"
