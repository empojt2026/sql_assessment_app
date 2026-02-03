import pandas as pd
import pathlib
import re

SUBMISSIONS = pathlib.Path(__file__).resolve().parents[1] / 'submissions'
SUBMISSIONS.mkdir(exist_ok=True)


def make_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def test_infer_email_from_filename(tmp_path, monkeypatch):
    f = tmp_path / "alice_at_company_com_20260203_000000.csv"
    rows = [{"question_id": 1, "question": "Q1", "your_answer": "A", "correct_answer": "A", "is_correct": True}]
    make_csv(f, rows)

    # simulate admin inference regex used in app
    m = re.search(r"([A-Za-z0-9._%+-]+_at_[A-Za-z0-9._%+-]+)", f.name)
    assert m
    candidate = m.group(1)
    candidate = re.sub(r'(_\d{6,16}.*)$', '', candidate)
    inferred = candidate.replace('_at_', '@').replace('_', '.')
    assert inferred == 'alice@company.com'


def test_infer_email_from_cell(tmp_path):
    f = tmp_path / "upload.csv"
    rows = [{"Name": "Bob", "Email": "bob@company.com", "question_id": 1}]
    make_csv(f, rows)

    df = pd.read_csv(f)
    # admin should find the email in a cell
    found = None
    for col in df.columns:
        for v in df[col].astype(str).head(10).values:
            if '@' in v:
                found = v
    assert found == 'bob@company.com'
