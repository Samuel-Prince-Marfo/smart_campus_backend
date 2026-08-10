"""Database seeding.

Replicates the frontend mock seed (`src/mock/seed.ts`) exactly: same IDs, emails,
courses, demo cohort and relative timestamps. Every demo account's password is
"password". Running `seed_database` clears all tables first, so it doubles as the
implementation behind POST /api/admin/reset-demo.
"""
from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from . import models
from .enrich import DEFAULT_SETTINGS
from .security import hash_password, iso_in_days, iso_in_hours

ACTIVE_YEAR = "2025/2026"
ACTIVE_SEMESTER = 1
CAMPUS = {"lat": 5.6502, "lng": -0.1869}

_ALL_MODELS = [
    models.AttendanceRecord,
    models.AttendanceSession,
    models.Submission,
    models.Assignment,
    models.CourseMaterial,
    models.ExamAttempt,
    models.Exam,
    models.Notification,
    models.AuditLog,
    models.Enrolment,
    models.Course,
    models.Program,
    models.Department,
    models.User,
    models.AppSetting,
]


def _sem_label(year: str, sem: int) -> str:
    return f"{year} · Sem {sem}"


def database_is_empty(db: Session) -> bool:
    return db.query(models.User).first() is None


def clear_all(db: Session) -> None:
    for model in _ALL_MODELS:
        db.execute(delete(model))
    db.flush()


def seed_database(db: Session) -> None:
    """Wipe and repopulate the database with the demo dataset."""
    clear_all(db)

    # --- Departments --------------------------------------------------------
    departments = [
        models.Department(department_id="d_cs", name="Computer Science", code="CS", hod_id="u_lect1", hod_name="Dr. Michael Opoku"),
        models.Department(department_id="d_is", name="Information Systems", code="IS", hod_id="u_lect4", hod_name="Prof. Akua Sarpong"),
        models.Department(department_id="d_ba", name="Business Administration", code="BA", hod_id="u_lect6", hod_name="Dr. Grace Adjei"),
        models.Department(department_id="d_ee", name="Electrical & Electronic Engineering", code="EEE", hod_id="u_lect8", hod_name="Dr. Yaw Darko"),
    ]
    db.add_all(departments)

    # --- Programs -----------------------------------------------------------
    programs = [
        models.Program(program_id="p_bcs", name="BSc Computer Science", code="BCS", department_id="d_cs", degree="BSc", duration_years=4),
        models.Program(program_id="p_bcy", name="BSc Cyber Security", code="BCY", department_id="d_cs", degree="BSc", duration_years=4),
        models.Program(program_id="p_bit", name="BSc Information Technology", code="BIT", department_id="d_is", degree="BSc", duration_years=4),
        models.Program(program_id="p_bis", name="BSc Information Systems", code="BIS", department_id="d_is", degree="BSc", duration_years=4),
        models.Program(program_id="p_bba_acc", name="BBA Accounting", code="ACC", department_id="d_ba", degree="BBA", duration_years=4),
        models.Program(program_id="p_bba_mkt", name="BBA Marketing", code="MKT", department_id="d_ba", degree="BBA", duration_years=4),
        models.Program(program_id="p_bee", name="BSc Electrical Engineering", code="BEE", department_id="d_ee", degree="BSc", duration_years=4),
    ]
    db.add_all(programs)
    prog_by_id = {p.program_id: p for p in programs}

    # --- Users --------------------------------------------------------------
    pw = hash_password("password")

    def U(**kw) -> models.User:
        kw.setdefault("password_hash", pw)
        return models.User(**kw)

    users = [
        # Admin
        U(user_id="u_admin", full_name="Ama Boateng", email="admin@campus.edu.gh", role="admin", department="ICT Directorate", avatar_color="#0f1d2b", created_at=iso_in_days(-400), active=True),
        # Computer Science lecturers
        U(user_id="u_lect1", full_name="Dr. Michael Opoku", email="lecturer@campus.edu.gh", role="lecturer", department="Computer Science", department_id="d_cs", is_hod=True, avatar_color="#b56b16", created_at=iso_in_days(-380), active=True),
        U(user_id="u_lect2", full_name="Dr. Kwabena Mensah", email="kwabena.mensah@campus.edu.gh", role="lecturer", department="Computer Science", department_id="d_cs", avatar_color="#7a4a12", created_at=iso_in_days(-360), active=True),
        U(user_id="u_lect3", full_name="Dr. Abena Owusu", email="abena.owusu@campus.edu.gh", role="lecturer", department="Computer Science", department_id="d_cs", avatar_color="#946016", created_at=iso_in_days(-350), active=True),
        # Information Systems lecturers
        U(user_id="u_lect4", full_name="Prof. Akua Sarpong", email="akua.sarpong@campus.edu.gh", role="lecturer", department="Information Systems", department_id="d_is", is_hod=True, avatar_color="#344251", created_at=iso_in_days(-370), active=True),
        U(user_id="u_lect5", full_name="Mr. Daniel Asante", email="daniel.asante@campus.edu.gh", role="lecturer", department="Information Systems", department_id="d_is", avatar_color="#4f6678", created_at=iso_in_days(-340), active=True),
        # Business Administration lecturers
        U(user_id="u_lect6", full_name="Dr. Grace Adjei", email="grace.adjei@campus.edu.gh", role="lecturer", department="Business Administration", department_id="d_ba", is_hod=True, avatar_color="#5b6f3a", created_at=iso_in_days(-360), active=True),
        U(user_id="u_lect7", full_name="Mr. Samuel Boadi", email="samuel.boadi@campus.edu.gh", role="lecturer", department="Business Administration", department_id="d_ba", avatar_color="#6f823a", created_at=iso_in_days(-330), active=True),
        # Electrical Engineering lecturers
        U(user_id="u_lect8", full_name="Dr. Yaw Darko", email="yaw.darko@campus.edu.gh", role="lecturer", department="Electrical & Electronic Engineering", department_id="d_ee", is_hod=True, avatar_color="#3a5b6f", created_at=iso_in_days(-350), active=True),
        # Students — BSc Computer Science · Level 300 (demo cohort)
        U(user_id="u_stu1", full_name="Joseph Abugah", email="student@campus.edu.gh", role="student", index_number="UEB3265022", program_id="p_bcs", program_name="BSc Computer Science", department_id="d_cs", department="Computer Science", level=300, admission_year="2023/2024", avatar_color="#cf8a1d", created_at=iso_in_days(-300), active=True),
        U(user_id="u_stu2", full_name="Bright Yeboah Sarfo", email="bright@campus.edu.gh", role="student", index_number="UEB3263422", program_id="p_bcs", program_name="BSc Computer Science", department_id="d_cs", department="Computer Science", level=300, admission_year="2023/2024", avatar_color="#4f6678", created_at=iso_in_days(-300), active=True),
        U(user_id="u_stu3", full_name="Clement Opoku Bawuah", email="clement@campus.edu.gh", role="student", index_number="UEB3262622", program_id="p_bcs", program_name="BSc Computer Science", department_id="d_cs", department="Computer Science", level=300, admission_year="2023/2024", avatar_color="#914e16", created_at=iso_in_days(-300), active=True),
        U(user_id="u_stu4", full_name="Prince Marfo Samuel", email="prince@campus.edu.gh", role="student", index_number="UEB3252022", program_id="p_bcs", program_name="BSc Computer Science", department_id="d_cs", department="Computer Science", level=300, admission_year="2023/2024", avatar_color="#6c8294", created_at=iso_in_days(-300), active=True),
        U(user_id="u_stu5", full_name="Felicity Koah", email="felicity@campus.edu.gh", role="student", index_number="UEB3255422", program_id="p_bcs", program_name="BSc Computer Science", department_id="d_cs", department="Computer Science", level=300, admission_year="2023/2024", avatar_color="#e3a52f", created_at=iso_in_days(-280), active=True),
        # BSc Computer Science · Level 200
        U(user_id="u_stu6", full_name="Nana Akua Frimpong", email="nana.frimpong@campus.edu.gh", role="student", index_number="UEB4112024", program_id="p_bcs", program_name="BSc Computer Science", department_id="d_cs", department="Computer Science", level=200, admission_year="2024/2025", avatar_color="#b56b16", created_at=iso_in_days(-200), active=True),
        U(user_id="u_stu7", full_name="Kojo Antwi", email="kojo.antwi@campus.edu.gh", role="student", index_number="UEB4112524", program_id="p_bcs", program_name="BSc Computer Science", department_id="d_cs", department="Computer Science", level=200, admission_year="2024/2025", avatar_color="#7a4a12", created_at=iso_in_days(-200), active=True),
        # BSc Cyber Security · Level 300
        U(user_id="u_stu8", full_name="Esi Mensa", email="esi.mensa@campus.edu.gh", role="student", index_number="UEB5132023", program_id="p_bcy", program_name="BSc Cyber Security", department_id="d_cs", department="Computer Science", level=300, admission_year="2023/2024", avatar_color="#946016", created_at=iso_in_days(-250), active=True),
        # BSc Information Technology · Level 300
        U(user_id="u_stu9", full_name="Akosua Adoma", email="akosua.adoma@campus.edu.gh", role="student", index_number="UEB6142023", program_id="p_bit", program_name="BSc Information Technology", department_id="d_is", department="Information Systems", level=300, admission_year="2023/2024", avatar_color="#344251", created_at=iso_in_days(-250), active=True),
        U(user_id="u_stu10", full_name="Yaw Boakye", email="yaw.boakye@campus.edu.gh", role="student", index_number="UEB6142523", program_id="p_bit", program_name="BSc Information Technology", department_id="d_is", department="Information Systems", level=300, admission_year="2023/2024", avatar_color="#4f6678", created_at=iso_in_days(-250), active=True),
        # BBA Accounting · Level 200
        U(user_id="u_stu11", full_name="Adwoa Pokuaa", email="adwoa.pokuaa@campus.edu.gh", role="student", index_number="UEB7152024", program_id="p_bba_acc", program_name="BBA Accounting", department_id="d_ba", department="Business Administration", level=200, admission_year="2024/2025", avatar_color="#5b6f3a", created_at=iso_in_days(-220), active=True),
        # BSc Electrical Engineering · Level 400
        U(user_id="u_stu12", full_name="Kwesi Appiah", email="kwesi.appiah@campus.edu.gh", role="student", index_number="UEB8162022", program_id="p_bee", program_name="BSc Electrical Engineering", department_id="d_ee", department="Electrical & Electronic Engineering", level=400, admission_year="2022/2023", avatar_color="#3a5b6f", created_at=iso_in_days(-330), active=True),
    ]
    db.add_all(users)

    # --- Courses ------------------------------------------------------------
    def mk(course_id, course_code, title, lecturer_id, program_id, level, semester_no, credits, description, year=ACTIVE_YEAR) -> models.Course:
        prog = prog_by_id[program_id]
        return models.Course(
            course_id=course_id, course_code=course_code, title=title, lecturer_id=lecturer_id,
            department_id=prog.department_id, program_id=program_id, program_name=prog.name,
            level=level, semester_no=semester_no, academic_year=year, semester=_sem_label(year, semester_no),
            credits=credits, description=description,
        )

    courses = [
        mk("c_cs301", "CSC 301", "Software Engineering", "u_lect1", "p_bcs", 300, 1, 3, "Principles and practice of building reliable software systems."),
        mk("c_cs305", "CSC 305", "Database Systems", "u_lect1", "p_bcs", 300, 1, 3, "Relational design, SQL, transactions and indexing."),
        mk("c_cs307", "CSC 307", "Operating Systems", "u_lect2", "p_bcs", 300, 1, 3, "Processes, scheduling, memory and file systems."),
        mk("c_cs309", "CSC 309", "Web Application Development", "u_lect3", "p_bcs", 300, 1, 3, "Modern client and server web technologies."),
        mk("c_cs302", "CSC 302", "Computer Networks", "u_lect2", "p_bcs", 300, 2, 3, "Layered network architecture, TCP/IP and routing."),
        mk("c_cs304", "CSC 304", "Artificial Intelligence", "u_lect3", "p_bcs", 300, 2, 3, "Search, knowledge representation and machine learning basics."),
        mk("c_cs201", "CSC 201", "Data Structures & Algorithms", "u_lect2", "p_bcs", 200, 1, 3, "Core data structures and algorithmic analysis."),
        mk("c_cs203", "CSC 203", "Object-Oriented Programming", "u_lect3", "p_bcs", 200, 1, 3, "OOP principles using Java."),
        mk("c_cs401", "CSC 401", "Distributed Systems", "u_lect3", "p_bcs", 400, 1, 3, "Consistency, replication and consensus."),
        mk("c_cy301", "CYB 301", "Network Security", "u_lect1", "p_bcy", 300, 1, 3, "Threat models, cryptography and secure protocols."),
        mk("c_it301", "ITC 301", "Systems Analysis & Design", "u_lect5", "p_bit", 300, 1, 3, "Requirements, modelling and system design."),
        mk("c_it303", "ITC 303", "Human–Computer Interaction", "u_lect4", "p_bit", 300, 1, 2, "Usability, interaction design and evaluation."),
        mk("c_acc201", "ACC 201", "Financial Accounting", "u_lect7", "p_bba_acc", 200, 1, 3, "Double-entry, ledgers and financial statements."),
        mk("c_ee401", "EEE 401", "Power Systems Analysis", "u_lect8", "p_bee", 400, 1, 3, "Load flow, fault analysis and stability."),
    ]
    db.add_all(courses)

    # --- Enrolments (auto-derived from program + level) ---------------------
    student_users = [u for u in users if u.role == "student"]
    for s in student_users:
        for c in courses:
            if c.program_id == s.program_id and c.level == s.level:
                db.add(models.Enrolment(enrolment_id=f"e_{c.course_id}_{s.user_id}", student_id=s.user_id, course_id=c.course_id, status="active"))

    # --- Attendance sessions + records --------------------------------------
    sessions = [
        models.AttendanceSession(session_id="as_live", course_id="c_cs301", course_code="CSC 301", lecturer_id="u_lect1", start_time=iso_in_hours(-0.2), end_time=iso_in_hours(1.5), geofence={"latitude": CAMPUS["lat"], "longitude": CAMPUS["lng"], "radius_m": 120, "label": "Engineering Block, Room E12"}, totp_seed="seed-cs301-live", rotate_seconds=15, status="open"),
        models.AttendanceSession(session_id="as_past1", course_id="c_cs305", course_code="CSC 305", lecturer_id="u_lect1", start_time=iso_in_days(-2), end_time=iso_in_days(-2), geofence={"latitude": CAMPUS["lat"], "longitude": CAMPUS["lng"], "radius_m": 120, "label": "Lab 2"}, totp_seed="seed-cs305-1", rotate_seconds=15, status="closed"),
        models.AttendanceSession(session_id="as_past2", course_id="c_cs307", course_code="CSC 307", lecturer_id="u_lect2", start_time=iso_in_days(-4), end_time=iso_in_days(-4), geofence={"latitude": CAMPUS["lat"], "longitude": CAMPUS["lng"], "radius_m": 100, "label": "Room E09"}, totp_seed="seed-cs307-1", rotate_seconds=15, status="closed"),
    ]
    db.add_all(sessions)

    def rec(rid, sid, stu, name, dev, when) -> models.AttendanceRecord:
        return models.AttendanceRecord(record_id=rid, session_id=sid, student_id=stu, student_name=name, status="present", device_id=dev, latitude=CAMPUS["lat"], longitude=CAMPUS["lng"], marked_at=when)

    db.add_all([
        rec("ar_1", "as_live", "u_stu2", "Bright Yeboah Sarfo", "dev_seed2", iso_in_hours(-0.1)),
        rec("ar_2", "as_live", "u_stu3", "Clement Opoku Bawuah", "dev_seed3", iso_in_hours(-0.05)),
        rec("ar_3", "as_past1", "u_stu1", "Joseph Abugah", "dev_seed1", iso_in_days(-2)),
        rec("ar_4", "as_past1", "u_stu2", "Bright Yeboah Sarfo", "dev_seed2", iso_in_days(-2)),
        rec("ar_5", "as_past1", "u_stu3", "Clement Opoku Bawuah", "dev_seed3", iso_in_days(-2)),
        rec("ar_6", "as_past1", "u_stu5", "Felicity Koah", "dev_seed5", iso_in_days(-2)),
        rec("ar_7", "as_past2", "u_stu1", "Joseph Abugah", "dev_seed1", iso_in_days(-4)),
        rec("ar_8", "as_past2", "u_stu4", "Prince Marfo Samuel", "dev_seed4", iso_in_days(-4)),
        rec("ar_9", "as_past2", "u_stu5", "Felicity Koah", "dev_seed5", iso_in_days(-4)),
    ])

    # --- Materials ----------------------------------------------------------
    db.add_all([
        models.CourseMaterial(material_id="m_1", course_id="c_cs301", course_code="CSC 301", title="Lecture 1 — Software Process Models", type="slides", file_key="files/cs301-l1.pptx", size_kb=2480, release_at=iso_in_days(-10), expires_at=None, uploaded_by="u_lect1", created_at=iso_in_days(-10), access_count=38),
        models.CourseMaterial(material_id="m_2", course_id="c_cs301", course_code="CSC 301", title="Reading — Agile vs Waterfall", type="pdf", file_key="files/cs301-agile.pdf", size_kb=910, release_at=iso_in_days(-8), expires_at=iso_in_days(30), uploaded_by="u_lect1", created_at=iso_in_days(-8), access_count=21),
        models.CourseMaterial(material_id="m_3", course_id="c_cs305", course_code="CSC 305", title="ER Modelling Notes", type="doc", file_key="files/cs305-er.docx", size_kb=540, release_at=iso_in_days(-5), expires_at=None, uploaded_by="u_lect1", created_at=iso_in_days(-5), access_count=17),
        models.CourseMaterial(material_id="m_4", course_id="c_cs307", course_code="CSC 307", title="CPU Scheduling Slides", type="slides", file_key="files/cs307-sched.pptx", size_kb=1900, release_at=iso_in_days(-3), expires_at=None, uploaded_by="u_lect2", created_at=iso_in_days(-3), access_count=12),
        models.CourseMaterial(material_id="m_5", course_id="c_cs309", course_code="CSC 309", title="Intro to React (video)", type="video", file_key="files/cs309-react.mp4", size_kb=0, release_at=iso_in_days(2), expires_at=None, uploaded_by="u_lect3", created_at=iso_in_days(-1), access_count=0),
    ])

    # --- Assignments + submissions ------------------------------------------
    db.add_all([
        models.Assignment(assignment_id="a_1", course_id="c_cs301", course_code="CSC 301", title="Requirements Specification Document", instructions="Produce an SRS for the case study system. Submit a single PDF.", deadline=iso_in_days(3), max_score=100, created_at=iso_in_days(-7)),
        models.Assignment(assignment_id="a_2", course_id="c_cs305", course_code="CSC 305", title="Normalize the Given Schema (3NF)", instructions="Normalize the supplied relation to 3NF and justify each step.", deadline=iso_in_days(-1), max_score=50, created_at=iso_in_days(-9)),
        models.Assignment(assignment_id="a_3", course_id="c_cs307", course_code="CSC 307", title="Scheduling Simulation", instructions="Implement and compare FCFS, SJF and Round Robin.", deadline=iso_in_days(7), max_score=100, created_at=iso_in_days(-3)),
    ])
    db.add_all([
        models.Submission(submission_id="s_1", assignment_id="a_1", student_id="u_stu1", student_name="Joseph Abugah", file_key="subs/a1-joseph.pdf", file_name="srs_joseph.pdf", score=None, feedback=None, submitted_at=iso_in_days(-1), graded_at=None, late=False),
        models.Submission(submission_id="s_2", assignment_id="a_1", student_id="u_stu2", student_name="Bright Yeboah Sarfo", file_key="subs/a1-bright.pdf", file_name="srs_bright.pdf", score=None, feedback=None, submitted_at=iso_in_hours(-5), graded_at=None, late=False),
        models.Submission(submission_id="s_3", assignment_id="a_2", student_id="u_stu1", student_name="Joseph Abugah", file_key="subs/a2-joseph.pdf", file_name="normalization.pdf", score=42, feedback="Good work. Watch the transitive dependency in step 3.", submitted_at=iso_in_days(-2), graded_at=iso_in_days(-1), late=False),
        models.Submission(submission_id="s_4", assignment_id="a_2", student_id="u_stu3", student_name="Clement Opoku Bawuah", file_key="subs/a2-clement.pdf", file_name="norm_clement.pdf", score=38, feedback="Solid, but 2NF justification is thin.", submitted_at=iso_in_days(-2), graded_at=iso_in_days(-1), late=False),
        models.Submission(submission_id="s_5", assignment_id="a_2", student_id="u_stu5", student_name="Felicity Koah", file_key="subs/a2-felicity.pdf", file_name="felicity_db.pdf", score=47, feedback="Excellent and complete.", submitted_at=iso_in_days(-3), graded_at=iso_in_days(-1), late=False),
    ])

    # --- Exams + attempts ---------------------------------------------------
    db.add_all([
        models.Exam(exam_id="x_1", course_id="c_cs301", course_code="CSC 301", title="Mid-Semester Quiz", duration_minutes=20, start_time=iso_in_hours(-1), end_time=iso_in_hours(24), shuffle=True, status="open", questions=[
            {"question_id": "q1", "prompt": "Which model emphasises fixed, sequential phases?", "options": ["Scrum", "Waterfall", "Kanban", "XP"], "correct_answer": 1, "points": 1},
            {"question_id": "q2", "prompt": "A user story is best described as…", "options": ["A UML diagram", "A short feature description from a user's perspective", "A test case", "A database table"], "correct_answer": 1, "points": 1},
            {"question_id": "q3", "prompt": "What does a sprint retrospective focus on?", "options": ["Writing code", "Process improvement", "Hiring", "Marketing"], "correct_answer": 1, "points": 1},
            {"question_id": "q4", "prompt": "Which is a non-functional requirement?", "options": ["The system shall allow login", "The system shall respond within 2 seconds", "The system shall store grades", "The system shall send emails"], "correct_answer": 1, "points": 1},
            {"question_id": "q5", "prompt": "Idempotency in sync means…", "options": ["Requests run faster", "Repeated requests don't create duplicates", "Data is encrypted", "Sessions never expire"], "correct_answer": 1, "points": 1},
        ]),
        models.Exam(exam_id="x_2", course_id="c_cs305", course_code="CSC 305", title="SQL Fundamentals Test", duration_minutes=30, start_time=iso_in_days(2), end_time=iso_in_days(2), shuffle=True, status="scheduled", questions=[
            {"question_id": "q1", "prompt": "Which clause filters grouped rows?", "options": ["WHERE", "HAVING", "ORDER BY", "LIMIT"], "correct_answer": 1, "points": 1},
            {"question_id": "q2", "prompt": "A primary key must be…", "options": ["Nullable", "Unique and not null", "A foreign key", "Indexed only"], "correct_answer": 1, "points": 1},
            {"question_id": "q3", "prompt": "Which join returns only matching rows?", "options": ["LEFT JOIN", "INNER JOIN", "FULL OUTER JOIN", "CROSS JOIN"], "correct_answer": 1, "points": 1},
        ]),
    ])
    db.add(models.ExamAttempt(attempt_id="att_1", exam_id="x_1", student_id="u_stu2", student_name="Bright Yeboah Sarfo", started_at=iso_in_hours(-0.6), submitted_at=iso_in_hours(-0.4), score=4, answers={"q1": 1, "q2": 1, "q3": 1, "q4": 1, "q5": 0}, question_order=["q1", "q2", "q3", "q4", "q5"], status="submitted", last_saved_at=iso_in_hours(-0.4)))

    # --- Notifications ------------------------------------------------------
    db.add_all([
        models.Notification(notification_id="n_1", user_id="u_stu1", type="attendance", title="Attendance open: CSC 301", body="Dr. Opoku started an attendance session in Room E12. Mark within 90 minutes.", read_at=None, created_at=iso_in_hours(-0.2)),
        models.Notification(notification_id="n_2", user_id="u_stu1", type="assignment", title="Deadline approaching", body="Requirements Specification Document is due in 3 days.", read_at=None, created_at=iso_in_hours(-3)),
        models.Notification(notification_id="n_3", user_id="u_stu1", type="exam", title="Quiz available", body="Mid-Semester Quiz for CSC 301 is now open.", read_at=iso_in_days(-0.04), created_at=iso_in_hours(-1)),
        models.Notification(notification_id="n_4", user_id="u_lect1", type="assignment", title="New submission", body="Bright Yeboah Sarfo submitted the Requirements Specification Document.", read_at=None, created_at=iso_in_hours(-5)),
        models.Notification(notification_id="n_5", user_id="u_admin", type="system", title="Backup completed", body="Nightly encrypted database backup completed successfully.", read_at=None, created_at=iso_in_hours(-8)),
    ])

    # --- Audit logs ---------------------------------------------------------
    db.add_all([
        models.AuditLog(log_id="l_1", actor_id="u_lect1", actor_name="Dr. Michael Opoku", action="attendance.session.start", target="CSC 301", ip_address="10.12.4.21", timestamp=iso_in_hours(-0.2)),
        models.AuditLog(log_id="l_2", actor_id="u_stu2", actor_name="Bright Yeboah Sarfo", action="attendance.mark", target="as_live", ip_address="10.12.7.55", timestamp=iso_in_hours(-0.1)),
        models.AuditLog(log_id="l_3", actor_id="u_admin", actor_name="Ama Boateng", action="user.create", target="u_stu5", ip_address="10.12.0.2", timestamp=iso_in_days(-1)),
        models.AuditLog(log_id="l_4", actor_id="u_lect1", actor_name="Dr. Michael Opoku", action="assignment.grade", target="s_3", ip_address="10.12.4.21", timestamp=iso_in_days(-1)),
    ])

    # --- Settings -----------------------------------------------------------
    settings_data = dict(DEFAULT_SETTINGS)
    settings_data["active_year"] = ACTIVE_YEAR
    settings_data["active_semester"] = ACTIVE_SEMESTER
    db.add(models.AppSetting(id=1, data=settings_data))

    db.commit()
