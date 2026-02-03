#!/usr/bin/env python3
"""Generate 5 test submissions for admin reporting."""

import os
import pandas as pd
import random
from datetime import datetime

# Test users
TEST_USERS = [
    ("alice_20260203_100000", "alice@company.com", 0.95),
    ("bob_20260203_110000", "bob@company.com", 0.75),
    ("charlie_20260203_120000", "charlie@company.com", 0.50),
    ("diana_20260203_130000", "diana@company.com", 0.85),
    ("eve_20260203_140000", "eve@company.com", 0.60),
]

def generate_submission(user_name, user_email, correctness_rate):
    """Generate a single test submission with randomized correctness."""
    # Total of 40 questions: 20 SQL + 20 MCQ
    num_questions = 40
    num_correct = int(num_questions * correctness_rate)
    
    questions = []
    correct_indices = set(random.sample(range(num_questions), num_correct))
    
    for i in range(num_questions):
        q_id = i + 1
        is_sql = i < 20
        is_correct = i in correct_indices
        
        if is_sql:
            question_type = "sql"
            question_text = f"SQL Question {q_id}"
            if is_correct:
                your_answer = f"SELECT * FROM table{q_id}"
                correct_answer = f"SELECT * FROM table{q_id}"
            else:
                your_answer = f"SELECT * FROM wrong_table{q_id}"
                correct_answer = f"SELECT * FROM table{q_id}"
        else:
            question_type = "mcq"
            question_text = f"MCQ Question {q_id}"
            options = ["A", "B", "C", "D"]
            if is_correct:
                your_answer = "A"
                correct_answer = "A"
            else:
                your_answer = random.choice(["B", "C", "D"])
                correct_answer = "A"
        
        questions.append({
            "Name": user_name,
            "Email": user_email,
            "question_id": q_id,
            "question": question_text,
            "your_answer": your_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "type": question_type
        })
    
    df = pd.DataFrame(questions)
    # Add summary columns
    correct_count = df["is_correct"].sum()
    total_count = len(df)
    score_pct = (correct_count / total_count * 100) if total_count > 0 else 0
    
    # Prepend summary row (for reference)
    summary = {
        "Name": user_name,
        "Email": user_email,
        "question_id": "SUMMARY",
        "question": "",
        "your_answer": "",
        "correct_answer": "",
        "is_correct": "",
        "type": "",
        "Correct Answers": correct_count,
        "Total Questions": total_count,
        "Score (%)": f"{score_pct:.1f}",
        "Submitted At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return df

def main():
    submissions_dir = "/workspaces/sql_assessment_app/sql_assessment_app/submissions"
    os.makedirs(submissions_dir, exist_ok=True)
    
    for user_name, user_email, correctness_rate in TEST_USERS:
        # Create filename from email (replace @ and . as app does)
        filename = user_email.replace('@', '_at_').replace('.', '_') + ".csv"
        filepath = os.path.join(submissions_dir, filename)
        
        df = generate_submission(user_name, user_email, correctness_rate)
        df.to_csv(filepath, index=False)
        correct_count = df["is_correct"].sum()
        total_count = len(df)
        score_pct = (correct_count / total_count * 100) if total_count > 0 else 0
        print(f"✓ Created {filename} ({score_pct:.1f}% correct, {correct_count}/{total_count} questions))")

if __name__ == "__main__":
    main()
    print("\n5 test submissions generated successfully!")
