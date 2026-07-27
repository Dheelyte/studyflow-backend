# Primerly Backend

The backend service for Primerly, an AI-powered platform for learning tech and digital skills. This service manages user authentication, curriculum generation using Google Gemini, playlist management, and community interactions.

## 🚀 Features

- **AI Curriculum Generation**: Generates structured learning paths (playlists) based on user prompts using Google's Gemini Pro model via LangChain.
- **Authentication**: secure JWT-based authentication with Argon2 hashing.
- **User Management**: Profile management, progress tracking.
- **Playlists & Modules**: Create, view, and track progress on learning playlists.
- **Community**: Discussion forums with posts and comments.
- **Rate Limiting**: Built-in API rate limiting using SlowAPI.
- **Async Architecture**: Fully asynchronous database and API operations.

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Database**: PostgreSQL (AsyncPG + SQLAlchemy 2.0)
- **Migrations**: Alembic
- **AI/LLM**: LangChain + Google Gemini
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Deployment**: Mangum (Ready for AWS Lambda)

## 📋 Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (Recommended for dependency management)
- PostgreSQL

## 🔧 Installation & Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd studyflow-backend
```

### 2. Install Dependencies
This project uses `uv` for fast package management.

```bash
uv sync
```
Or with standard pip:
```bash
pip install -r requirements.txt
```
*(Note: If requirements.txt is not present, use `pip install .` or rely on `uv`)*

### 3. Configure Environment Variables
Create a `.env` file in the root directory. You can reference `app/config.py` for all available options.

```ini
# Core
ENVIRONMENT=dev
DEBUG=True
SECRET_KEY=your_super_secret_key_min_32_chars
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/studyflow

# Security
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRES_MINUTES=300
CORS_ALLOWED_ORIGINS=["http://localhost:3000"]

# Google Gemini (Required for AI features)
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-pro

# Mail Server (For password reset - Optional in dev)
MAIL_USERNAME=test
MAIL_PASSWORD=test
MAIL_FROM=test@email.com
MAIL_PORT=587
MAIL_SERVER=smtp.example.com
```

### 4. Database Setup
Run migrations to set up the database schema.

```bash
uv run alembic upgrade head
```

## 🏃‍♂️ Running the Application

Start the development server:

```bash
uv run fastapi dev app/main.py
```

The API will be available at `http://127.0.0.1:8000`.

## 📚 API Documentation

FastAPI provides interactive API documentation automatically. Once the server is running, visit:

- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## 📁 Project Structure

```
studyflow-backend/
├── app/
│   ├── chains/         # LangChain logic for AI generation
│   ├── db/            # Database session and connection
│   ├── dependencies/  # FastAPI dependencies (auth, etc.)
│   ├── exceptions/    # Custom exception handlers
│   ├── middlewares/   # Custom middlewares (CORS, timing, etc.)
│   ├── models/        # SQLAlchemy database models
│   ├── prompts/       # LLM prompts
│   ├── repositories/  # Data access layer
│   ├── routers/       # API route definitions
│   ├── schema/        # Pydantic schemas (request/response models)
│   ├── services/      # Business logic layer
│   └── main.py        # Application entry point
├── alembic/           # Database migrations
├── tests/             # Test suite
└── pyproject.toml     # Project configuration
```

## 🧪 Running Tests

```bash
uv run pytest
```
