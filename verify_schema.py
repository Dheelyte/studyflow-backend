from app.schema.quiz import QuizResponse, Question, Option

def test_quiz_response_id():
    questions = [
        Question(
            id=1,
            text="Q1",
            options=[Option(id="a", text="A")],
            correctOptionId="a"
        )
    ]
    
    # Simulate DB object with attributes
    class MockQuiz:
        def __init__(self):
            self.module_id = 123
            self.questions = questions
            self.id = 1 # DB ID
            self.module = None # mocking relationship if needed
    
    mock_db_quiz = MockQuiz()
    
    # Convert to Pydantic
    response = QuizResponse.model_validate(mock_db_quiz)
    
    print(f"Computed ID: {response.id}")
    expected_id = "quiz_123"
    assert response.id == expected_id, f"Expected {expected_id}, got {response.id}"
    print("Verification Passed!")

if __name__ == "__main__":
    test_quiz_response_id()
