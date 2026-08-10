"""SQLAlchemy ORM models.

Mirrors the domain types in the frontend's `src/types/index.ts`. Timestamps are
stored as ISO 8601 strings (matching the frontend's conventions exactly), and
nested structures (geofence, exam questions, attempt answers) use JSON columns.
"""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # student|lecturer|admin
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    index_number: Mapped[str | None] = mapped_column(String, nullable=True)
    department: Mapped[str | None] = mapped_column(String, nullable=True)       # display name
    department_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_hod: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    program_id: Mapped[str | None] = mapped_column(String, nullable=True)
    program_name: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admission_year: Mapped[str | None] = mapped_column(String, nullable=True)

    avatar_color: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Department(Base):
    __tablename__ = "departments"

    department_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    hod_id: Mapped[str | None] = mapped_column(String, nullable=True)
    hod_name: Mapped[str | None] = mapped_column(String, nullable=True)


class Program(Base):
    __tablename__ = "programs"

    program_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    department_id: Mapped[str] = mapped_column(String, nullable=False)
    degree: Mapped[str] = mapped_column(String, default="BSc", nullable=False)
    duration_years: Mapped[int] = mapped_column(Integer, default=4, nullable=False)


class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[str] = mapped_column(String, primary_key=True)
    course_code: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    lecturer_id: Mapped[str] = mapped_column(String, nullable=False)
    department_id: Mapped[str | None] = mapped_column(String, nullable=True)
    program_id: Mapped[str | None] = mapped_column(String, nullable=True)
    program_name: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    semester_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String, nullable=True)
    semester: Mapped[str | None] = mapped_column(String, nullable=True)  # display label
    credits: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Enrolment(Base):
    __tablename__ = "enrolments"

    enrolment_id: Mapped[str] = mapped_column(String, primary_key=True)
    student_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    course_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    course_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    course_code: Mapped[str | None] = mapped_column(String, nullable=True)
    lecturer_id: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[str] = mapped_column(String, nullable=False)
    end_time: Mapped[str] = mapped_column(String, nullable=False)
    geofence: Mapped[dict] = mapped_column(JSON, nullable=False)
    totp_seed: Mapped[str] = mapped_column(String, nullable=False)
    rotate_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    record_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    student_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # present|absent|rejected
    device_id: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    marked_at: Mapped[str] = mapped_column(String, nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class CourseMaterial(Base):
    __tablename__ = "materials"

    material_id: Mapped[str] = mapped_column(String, primary_key=True)
    course_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    course_code: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # pdf|slides|video|link|doc
    file_key: Mapped[str] = mapped_column(String, nullable=False)
    size_kb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    release_at: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str | None] = mapped_column(String, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id: Mapped[str] = mapped_column(String, primary_key=True)
    course_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    course_code: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    deadline: Mapped[str] = mapped_column(String, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Submission(Base):
    __tablename__ = "submissions"

    submission_id: Mapped[str] = mapped_column(String, primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    student_name: Mapped[str | None] = mapped_column(String, nullable=True)
    file_key: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[str] = mapped_column(String, nullable=False)
    graded_at: Mapped[str | None] = mapped_column(String, nullable=True)
    late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Exam(Base):
    __tablename__ = "exams"

    exam_id: Mapped[str] = mapped_column(String, primary_key=True)
    course_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    course_code: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    start_time: Mapped[str] = mapped_column(String, nullable=False)
    end_time: Mapped[str] = mapped_column(String, nullable=False)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String, default="scheduled", nullable=False)


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    attempt_id: Mapped[str] = mapped_column(String, primary_key=True)
    exam_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    student_name: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    question_order: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String, default="in_progress", nullable=False)
    last_saved_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    read_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id: Mapped[str] = mapped_column(String, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target: Mapped[str] = mapped_column(String, default="", nullable=False)
    ip_address: Mapped[str] = mapped_column(String, default="", nullable=False)
    timestamp: Mapped[str] = mapped_column(String, nullable=False)


class AppSetting(Base):
    """Single-row table holding the institution settings object as JSON."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
