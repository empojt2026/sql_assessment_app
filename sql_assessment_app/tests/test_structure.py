import os


def test_project_structure_exists():
    # repo root is one level above the package folder
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    assert os.path.exists(os.path.join(root, 'streamlit_app.py'))
    assert os.path.exists(os.path.join(root, 'requirements.txt'))
    submissions = os.path.join(root, 'sql_assessment_app', 'submissions')
    assert os.path.isdir(submissions)
    # submissions should be writable (at least in CI/dev envs)
    assert os.access(submissions, os.W_OK)
