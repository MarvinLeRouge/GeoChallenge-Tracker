
from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, conlist
from datetime import datetime
from app.core.bson_utils import PyObjectId
from app.models.challenge_ast import TaskExpression

class TaskIn(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, description="Task id if updating")
    title: Optional[str] = Field(default=None, max_length=200)
    expression: TaskExpression = Field(..., description="AST expression for this task")
    constraints: Dict[str, Any] = Field(..., description="Ex: {'min_count': 4}")
    status: Optional[str] = Field(default=None, description="Optional manual status: 'todo' | 'in_progress' | 'done'")

class TasksPutIn(BaseModel):
    tasks: conlist(TaskIn, min_items=0, max_items=50)

class TasksValidateIn(BaseModel):
    tasks: conlist(TaskIn, min_items=0, max_items=50)

class TaskOut(BaseModel):
    id: PyObjectId
    order: int
    title: str
    expression: TaskExpression
    constraints: Dict[str, Any]
    status: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, Any]] = None
    last_evaluated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

class TasksListResponse(BaseModel):
    items: List[TaskOut]

class ValidationErrorItem(BaseModel):
    index: int
    field: str
    code: str
    message: str

class TasksValidateResponse(BaseModel):
    ok: bool
    errors: List[ValidationErrorItem] = []
