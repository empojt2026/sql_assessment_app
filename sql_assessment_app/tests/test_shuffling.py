import ast
import inspect

SRC = open(__file__.replace('tests/test_shuffling.py', 'app.py')).read()
MODULE = ast.parse(SRC)

# extract QUESTIONS and POWERBI_QUESTIONS using AST literal_eval
def _extract_constant(name):
    for node in MODULE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, 'id', None) == name:
                    return ast.literal_eval(node.value)
    raise RuntimeError(f'{name} not found')

QUESTIONS = _extract_constant('QUESTIONS')
POWERBI_QUESTIONS = _extract_constant('POWERBI_QUESTIONS')

# extract get_shuffled_questions source and exec in a sandboxed namespace
for node in MODULE.body:
    if isinstance(node, ast.FunctionDef) and node.name == 'get_shuffled_questions':
        fn_src = ''.join(SRC.splitlines(True)[node.lineno - 1: node.end_lineno])
        break
else:
    raise RuntimeError('get_shuffled_questions not found')

ns = {'random': __import__('random'), 'hashlib': __import__('hashlib'), 'QUESTIONS': QUESTIONS, 'POWERBI_QUESTIONS': POWERBI_QUESTIONS}
exec(fn_src, ns)
get_shuffled_questions = ns['get_shuffled_questions']


def test_shuffled_questions_length_and_composition():
    user = "test.user@example.com"
    shuffled = get_shuffled_questions(user)

    # total questions
    assert isinstance(shuffled, list)
    assert len(shuffled) == 40, "Each candidate must receive 40 questions"

    # composition: 20 SQL (split into 10 MCQ + 10 practice SQL)
    sql_qs = [q for q in shuffled if q in QUESTIONS]
    assert len(sql_qs) == 20, "There must be exactly 20 SQL questions"

    # enforce 10 MCQ and 10 practice SQL (type-based)
    sql_mcq_count = sum(1 for q in sql_qs if q.get('type') == 'mcq')
    # practice SQL items are represented as questions with a 'solution' (no type == 'mcq')
    sql_practice_count = sum(1 for q in sql_qs if q.get('type') != 'mcq')
    assert sql_mcq_count == 10 and sql_practice_count == 10, f"Expected 10 SQL MCQ and 10 SQL practice (got mcq={sql_mcq_count}, practice={sql_practice_count})"

    # verify practice SQL items still have solutions and are not too complex
    for q in (q for q in sql_qs if q.get('type') == 'sql'):
        assert q.get("solution"), "SQL practice question must have a solution"
        # must not contain multiple JOINs
        assert q['solution'].lower().count('join') <= 1
        # compute complexity with same heuristic used by the app (lightweight)
        sol = q.get('solution', '').lower()
        joins = sol.count('join')
        group_by = sol.count('group by')
        having = sol.count('having')
        case_when = sol.count('case')
        subquery = sol.count('select') > 1
        distinct = sol.count('distinct')
        complexity_score = 0
        if joins > 0:
            complexity_score += joins * 2
        if group_by > 0:
            complexity_score += 1
        if having > 0:
            complexity_score += 1
        if case_when > 0:
            complexity_score += 2
        if subquery:
            complexity_score += 2
        if distinct:
            complexity_score += 0.5
        if len(q.get('tables', [])) > 2:
            complexity_score += 1
        inferred = 3 if complexity_score >= 4 else (2 if complexity_score >= 1.5 else 1)
        assert inferred in (1, 2), f"Question {q.get('id')} is inferred advanced but was selected: score={complexity_score}"

    # composition: 20 PowerBI (prefer complexity 1, allow complexity 2)
    pb_qs = [q for q in shuffled if q in POWERBI_QUESTIONS]
    assert len(pb_qs) == 20, "There must be exactly 20 PowerBI questions"
    # ensure we prefer easy questions when available
    def _complexity_value(q):
        c = q.get('complexity', 1)
        if isinstance(c, int):
            return c
        if isinstance(c, str):
            return {'easy': 1, 'medium': 2, 'hard': 3}.get(c.lower(), 2)
        try:
            return int(c)
        except Exception:
            return 2

    easy_count = sum(1 for q in pb_qs if _complexity_value(q) == 1)
    available_easy = sum(1 for q in POWERBI_QUESTIONS if _complexity_value(q) == 1)
    if available_easy > 0:
        assert easy_count > 0, "At least one easy PowerBI question should be present when easy questions exist in the bank"


def test_shuffled_is_deterministic_per_user():
    a = get_shuffled_questions("Alice")
    b = get_shuffled_questions("Alice")
    c = get_shuffled_questions("Bob")
    assert a == b
    assert a != c
