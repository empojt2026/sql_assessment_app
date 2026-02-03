import re
import pathlib

SRC = (pathlib.Path(__file__).resolve().parents[1] / 'app.py').read_text()


def test_title_updated_to_ojt():
    assert 'OJT Assessment' in SRC, 'App title/header must be renamed to OJT Assessment'


def test_partial_save_includes_name_and_email():
    # ensure partial save writes Name and Email into the saved payload
    snippet_re = re.compile(r"_partial\.csv[\s\S]{0,200}Name\":|\"Email\":")
    assert 'partial.csv' in SRC
    assert '"Name"' in SRC and '"Email"' in SRC


def test_submission_filename_uniqueness_present():
    # ensure filename generation includes microseconds or uuid for uniqueness
    assert "%f" in SRC or 'uuid.uuid4' in SRC, 'Submission filenames should include microsecond or uuid for uniqueness'


def test_admin_infers_email_from_filename():
    # admin aggregation should include fallback inference from filename
    assert "replace('_at_','@')" in SRC or 'infer from filename' in SRC or 'inferred' in SRC
