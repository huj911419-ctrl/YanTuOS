from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Subject = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20000)]
KnowledgeStatus = Literal["unstarted", "learning", "consolidating", "mastered"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Versioned(Input):
    expected_revision: int | None = Field(default=None, ge=1)


class TaskInput(Versioned):
    title: ShortText
    subject: Subject = "数学"
    scheduled_date: date
    estimated_minutes: int = Field(default=30, ge=1, le=1440)
    notes: LongText = ""
    completed: bool = False
    priority: int = Field(default=2, ge=1, le=3)
    goal_id: int | None = None
    status: Literal["todo", "doing", "done"] = "todo"


class TaskCompletion(Input):
    completed: bool


class KnowledgeInput(Versioned):
    title: ShortText
    domain: Subject = "自定义"
    subject: Subject = "数学"
    parent_id: int | None = None
    mastery: int = Field(default=0, ge=0, le=5)
    exam_scopes: list[Literal["math1", "math2", "math3"]] = Field(
        default_factory=list, max_length=3
    )
    syllabus_source: str = Field(default="", max_length=500)
    syllabus_year: int | None = Field(default=None, ge=2000, le=2100)
    status: KnowledgeStatus = "unstarted"
    notes: LongText = ""


class KnowledgeState(Input):
    status: KnowledgeStatus


class SessionInput(Input):
    subject: Subject
    topic: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    mode: Literal["forward", "pomodoro"] = "forward"
    target_minutes: int = Field(default=25, ge=1, le=180)
    break_minutes: int = Field(default=5, ge=1, le=60)
    request_id: str | None = Field(default=None, min_length=8, max_length=100)


class SessionFinish(Input):
    notes: LongText = ""


class MistakeInput(Versioned):
    title: ShortText
    subject: Subject = "数学"
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
    ]
    answer: LongText = ""
    wrong_answer: LongText = ""
    category: Subject = "未分类"
    mastery: Literal["unmastered", "reviewing", "mastered"] = "unmastered"
    file_ids: list[str] = Field(default_factory=list, max_length=10)
    error_reason: LongText = ""
    source: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = (
        ""
    )
    knowledge_ids: list[int] = Field(default_factory=list, max_length=100)


class ReviewInput(Input):
    outcome: Literal["remembered", "forgotten", "assisted"]
    notes: LongText = ""


class AIQuestion(Input):
    question: ShortText
