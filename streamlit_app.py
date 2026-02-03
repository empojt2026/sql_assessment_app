# Lightweight wrapper so Streamlit (Cloud/Share) can run the app from the repository root.
# It executes the existing app script as __main__ so relative paths continue to work.
import runpy

if __name__ == "__main__":
    runpy.run_path("sql_assessment_app/app.py", run_name="__main__")
