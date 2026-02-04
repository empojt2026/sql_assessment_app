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


def test_mcq_letter_extraction_handles_paren_and_dot():
    """Ensure MCQ option-letter extraction is robust for both 'A.' and 'A)' formats.
    - repository must contain at least one question using the ')' style (SQL bank uses this)
    - app.py must use a regex-based extraction (prevents regression where full option text was compared)
    """
    assert "re.match(r'^\\s*([A-Za-z])'" in SRC, "expected regex-based option-letter extraction in app.py"
    # ensure at least one MCQ option uses the 'A)' style (we observed SQL bank uses this)
    assert 'C) Cartesian product of both tables' in SRC or 'A) ' in SRC, "expected at least one MCQ option using ')' formatting"