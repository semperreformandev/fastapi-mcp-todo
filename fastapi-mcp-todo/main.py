from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Column, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Database setup (SQLite + SQLAlchemy)
SQLALCHEMY_DATABASE_URL = "sqlite:///./todos.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# SQLAlchemy model for todos table
class TodoItem(Base):
    __tablename__ = "todos"

    todo_id = Column(Integer, primary_key=True, index=True)
    content = Column(String, index=True)
    completed = Column(Boolean, default=False)


# Create the database table
Base.metadata.create_all(bind=engine)


# Pydantic models for request and response validation
class TodoBase(BaseModel):
    content: str
    completed: bool = False


class TodoCreate(TodoBase):
    pass


class Todo(TodoBase):
    todo_id: int

    model_config = ConfigDict(from_attributes=True)


# Dependency to manage database sessions
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]

# FastAPI app instance with metadata
app = FastAPI(
    title="Todo API",
    description="A simple Todo API built with FastAPI",
    version="1.0.0",
)


# Root route with HTML response
@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return "<h2>Welcome to the Todo API!</h2>"


@app.get("/todos/", response_model=list[Todo], operation_id="get_all_todos")
def read_todos(db: SessionDep, skip: int = 0, limit: int = 100):
    """Get all todo items with optional pagination."""
    todos = db.query(TodoItem).offset(skip).limit(limit).all()
    return todos


@app.get("/todos/{todo_id}", response_model=Todo, operation_id="get_todo")
def read_todo(todo_id: int, db: SessionDep):
    """Get a specific todo item by ID."""
    todo = db.query(TodoItem).filter(TodoItem.todo_id == todo_id).first()
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@app.post("/todos/", response_model=Todo, operation_id="create_todo")
def create_todo(todo: TodoCreate, db: SessionDep):
    """Create a new todo item."""
    db_todo = TodoItem(**todo.model_dump())
    db.add(db_todo)
    db.commit()
    db.refresh(db_todo)
    return db_todo


@app.put("/todos/{todo_id}", response_model=Todo, operation_id="update_todo")
def update_todo(todo_id: int, todo: TodoCreate, db: SessionDep):
    """Update an existing todo item."""
    db_todo = db.query(TodoItem).filter(TodoItem.todo_id == todo_id).first()
    if db_todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")

    for key, value in todo.model_dump().items():
        setattr(db_todo, key, value)

    db.commit()
    db.refresh(db_todo)
    return db_todo


@app.delete("/todos/{todo_id}", operation_id="delete_todo")
def delete_todo(todo_id: int, db: SessionDep):
    """Delete a todo item."""
    db_todo = db.query(TodoItem).filter(TodoItem.todo_id == todo_id).first()
    if db_todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")

    db.delete(db_todo)
    db.commit()
    return {"message": "Todo deleted successfully"}


# if __name__ == "__main__":
# import uvicorn

# Expose selected routes via MCP for LLM compatibility
mcp = FastApiMCP(
    app,
    include_operations=[
        "get_all_todos",
        "get_todo",
        "create_todo",
        "update_todo",
        "delete_todo",
    ],
)
mcp.mount_http()

# To run: uvicorn main:app --reload
# Docs: http://localhost:8000/docs
