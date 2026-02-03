import ast
import inspect
import textwrap


def _load_parse_fn():
    src = open(__file__.replace('tests/test_parsing.py', 'app.py')).read()
    module = ast.parse(src)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'parse_sample_text':
            fn_src = ast.get_source_segment(src, node)
            break
    else:
        raise RuntimeError('parse_sample_text not found in app.py')

    ns = {}
    exec(fn_src, ns)
    return ns['parse_sample_text']


def test_parse_io_format():
    parse = _load_parse_fn()
    res = parse("input_val ? output_val")
    assert res['type'] == 'io'
    assert res['input'] == 'input_val'
    assert res['output'] == 'output_val'


def test_parse_kv_format():
    parse = _load_parse_fn()
    res = parse("a: 1, b: 2")
    assert res['type'] == 'kv'
    assert isinstance(res['rows'], list)
    assert any(r['Column'] == 'a' and r['Value'] == '1' for r in res['rows'])


def test_parse_text_fallback():
    parse = _load_parse_fn()
    res = parse("Just some text")
    assert res['type'] == 'text'
    assert res['text'] == 'Just some text'
