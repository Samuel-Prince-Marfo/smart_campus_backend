"""Pydantic request schemas.

These validate incoming request bodies. Responses are returned as plain dicts
assembled by `app/enrich.py`, so the JSON shape matches the frontend's TypeScript
interfaces exactly (no fields dropped or renamed by a response model).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ----- Auth -----------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str = "student"
    index_number: Optional[str] = None
    department_id: Optional[str] = None
    program_id: Optional[str] = None
    level: Optional[int] = None
    admission_year: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class RefreshRequest(BaseModel):
    refresh_token: str


# ----- Institution ----------------------------------------------------------
class DepartmentCreate(BaseModel):
    name: str
    code: str
    hod_id: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    hod_id: Optional[str] = None


class ProgramCreate(BaseModel):
    name: str
    code: str
    department_id: str
    degree: Optional[str] = "BSc"
    duration_years: Optional[int] = 4


class AcademicPeriodUpdate(BaseModel):
    academic_year: Optional[str] = None
    semester: Optional[int] = None


# ----- Courses --------------------------------------------------------------
class CourseCreate(BaseModel):
    course_code: str
    title: str
    credits: Optional[int] = 3
    description: Optional[str] = None
    program_id: Optional[str] = None
    level: Optional[int] = None
    semester_no: Optional[int] = None
    academic_year: Optional[str] = None
    lecturer_id: Optional[str] = None


# ----- Attendance -----------------------------------------------------------
class Geofence(BaseModel):
    latitude: float
    longitude: float
    radius_m: float
    label: str


class AttendanceSessionCreate(BaseModel):
    course_id: str
    geofence: Geofence
    duration_minutes: Optional[int] = 90


class AttendanceMark(BaseModel):
    token: str
    latitude: float
    longitude: float
    device_id: str


# ----- Materials ------------------------------------------------------------
class MaterialCreate(BaseModel):
    course_id: str
    title: str
    type: str
    size_kb: Optional[int] = 0
    release_at: Optional[str] = None
    expires_at: Optional[str] = None


# ----- Assignments ----------------------------------------------------------
class AssignmentCreate(BaseModel):
    course_id: str
    title: str
    instructions: str = ""
    deadline: str
    max_score: Optional[int] = 100


class SubmissionCreate(BaseModel):
    file_name: str


class GradeRequest(BaseModel):
    score: float
    feedback: Optional[str] = ""


# ----- Exams ----------------------------------------------------------------
class ExamQuestionIn(BaseModel):
    question_id: Optional[str] = None
    prompt: str
    options: List[str]
    correct_answer: int
    points: int = 1


class ExamCreate(BaseModel):
    course_id: str
    title: str
    duration_minutes: Optional[int] = 20
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    shuffle: Optional[bool] = True
    questions: Optional[List[ExamQuestionIn]] = None
    status: Optional[str] = "scheduled"


class AttemptSave(BaseModel):
    answers: Dict[str, int] = Field(default_factory=dict)


class AttemptSubmit(BaseModel):
    answers: Optional[Dict[str, int]] = None
    auto: Optional[bool] = False


# ----- Admin ----------------------------------------------------------------
class AdminUserCreate(BaseModel):
    full_name: str
    email: EmailStr
    role: str
    password: Optional[str] = None
    department_id: Optional[str] = None
    program_id: Optional[str] = None
    level: Optional[int] = None
    index_number: Optional[str] = None
    is_hod: Optional[bool] = None
    admission_year: Optional[str] = None


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    index_number: Optional[str] = None
    department_id: Optional[str] = None
    is_hod: Optional[bool] = None
    program_id: Optional[str] = None
    level: Optional[int] = None
    admission_year: Optional[str] = None
    avatar_color: Optional[str] = None
    active: Optional[bool] = None


class SettingsUpdate(BaseModel):
    # Free-form: any subset of the settings object may be patched.
    model_config = {"extra": "allow"}

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_unset=True)
