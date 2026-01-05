from app.schema.quiz import QuizResponse, Question, Option
from app.schema.module import ModuleResponse
from app.schema.playlist import PlaylistDetailSchema, ModuleRead

def test_quiz_response_id():
    questions = [
        Question(
            id=1,
            text="Q1",
            options=[Option(id="a", text="A")],
            correctOptionId="a"
        )
    ]
    
    # Simulate DB object
    class MockQuiz:
        def __init__(self):
            self.module_id = 123
            self.questions = questions
            self.id = 1 # DB ID
    
    mock_db_quiz = MockQuiz()
    
    # Convert to Pydantic
    response = QuizResponse.model_validate(mock_db_quiz)
    
    print(f"Computed ID: {response.id}")
    expected_id = 1
    assert response.id == expected_id, f"Expected {expected_id}, got {response.id}"
    print("Quiz ID Verification Passed!")

def test_module_no_quiz():
    # Verify ModuleResponse does NOT have quiz
    if 'quiz' in ModuleResponse.model_fields:
        print("FAIL: ModuleResponse still has 'quiz' field")
    else:
        print("PASS: ModuleResponse does not have 'quiz' field")

    # Verify ModuleRead (in playlist schema) does NOT have quiz
    if 'quiz' in ModuleRead.model_fields:
        print("FAIL: ModuleRead still has 'quiz' field")
    else:
        print("PASS: ModuleRead does not have 'quiz' field")

if __name__ == "__main__":
    test_quiz_response_id()
    test_module_no_quiz()
