"""
database.py - Database initialisation utilities for the College Management System.

Provides helpers for:
- Creating all tables
- Seeding roles, permissions, and role_permission relationships
- Creating the initial administrator account
- Checking database connectivity
"""

import logging
import os
import time
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def init_db(app) -> None:
    """
    Create all database tables defined in the SQLAlchemy metadata.
    """
    import models  # Registers all models with SQLAlchemy metadata
    from extensions import db

    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created (or verified) successfully.")
        except SQLAlchemyError as exc:
            logger.exception("Failed to create database tables: %s", exc)
            raise


def seed_roles(app=None) -> None:
    """
    Seed roles, permissions, and role_permission mappings.
    Idempotent and safe to run on every deployment.
    """
    from extensions import db
    from models import Role, Permission, RolePermission
    from security.permissions import (
        ADMIN_PERMISSIONS,
        FACULTY_PERMISSIONS,
        STUDENT_PERMISSIONS,
    )

    def _seed():
        # 1. Seed Roles
        roles_data = [
            ("Admin", "Full system superuser access. Complete authority over all modules."),
            ("Faculty", "Broad academic access for assigned departments, classes and subjects."),
            ("Student", "Restricted access to own academic records, attendance, and MCQ exams."),
        ]

        role_objects = {}
        for r_name, r_desc in roles_data:
            role = Role.query.filter_by(role_name=r_name).first()
            if not role:
                role = Role(role_name=r_name, description=r_desc)
                db.session.add(role)
                db.session.flush()
                logger.info("Created role: %s", r_name)
            role_objects[r_name] = role

        # 2. Seed Permissions
        all_perms = set()
        all_perms.update(ADMIN_PERMISSIONS)
        all_perms.update(FACULTY_PERMISSIONS)
        all_perms.update(STUDENT_PERMISSIONS)

        perm_objects = {}
        for p_name in sorted(all_perms):
            perm = Permission.query.filter_by(permission_name=p_name).first()
            if not perm:
                category = p_name.split("_")[0].lower() if "_" in p_name else "general"
                perm = Permission(
                    permission_name=p_name,
                    description=p_name.replace("_", " ").title(),
                    category=category,
                )
                db.session.add(perm)
                db.session.flush()
            perm_objects[p_name] = perm

        # 3. Seed RolePermissions
        role_map = {
            "Admin": ADMIN_PERMISSIONS,
            "Faculty": FACULTY_PERMISSIONS,
            "Student": STUDENT_PERMISSIONS,
        }

        for r_name, p_set in role_map.items():
            role = role_objects[r_name]
            for p_name in p_set:
                perm = perm_objects[p_name]
                link = RolePermission.query.filter_by(
                    role_id=role.id, permission_id=perm.id
                ).first()
                if not link:
                    link = RolePermission(role_id=role.id, permission_id=perm.id)
                    db.session.add(link)

        db.session.commit()
        logger.info("Roles and permissions successfully seeded.")

    if app is not None:
        with app.app_context():
            _seed()
    else:
        _seed()


def seed_academic_structure(app=None) -> None:
    """Ensure departments, semesters, and four class sections exist for registration."""
    from extensions import db
    from models import AcademicYear, ClassSection, Department, Semester, Subject

    departments_data = [
        ("Computer Science and Engineering", "CSE", "CSE Department"),
        ("Electronics and Communication Engineering", "ECE", "ECE Department"),
        ("Artificial Intelligence and Machine Learning", "AIML", "AIML Department"),
        ("Mechanical Engineering", "MECH", "Mechanical Engineering Department"),
        ("Civil Engineering", "CIVIL", "Civil Engineering Department"),
        ("Electrical and Electronics Engineering", "EEE", "EEE Department"),
    ]
    section_names = ("A", "B", "C", "D")
    subjects_by_department = {
        "CSE": [
            "Data Structures and Algorithms",
            "Object-Oriented Programming (Java/C++)",
            "Database Management Systems (DBMS)",
            "Operating Systems",
            "Computer Networks",
            "Software Engineering",
            "Compiler Design",
        ],
        "AIML": [
            "Python/R Programming",
            "Linear Algebra and Statistics",
            "Machine Learning Algorithms",
            "Deep Learning and Neural Networks",
            "Natural Language Processing (NLP)",
            "Computer Vision",
            "Reinforcement Learning",
        ],
        "ECE": [
            "Network Analysis and Synthesis",
            "Electronic Devices and Circuits (EDC)",
            "Digital Electronics",
            "Signals and Systems",
            "Microprocessors and Microcontrollers",
            "Electromagnetic Theory",
            "VLSI Design",
        ],
        "EEE": [
            "Circuit Theory",
            "Electrical Machines (AC/DC)",
            "Power Systems",
            "Control Systems",
            "Power Electronics",
            "Electrical Measurements and Instrumentation",
            "Renewable Energy Sources",
        ],
        "MECH": [
            "Engineering Mechanics",
            "Thermodynamics",
            "Fluid Mechanics and Machinery",
            "Strength of Materials",
            "Kinematics and Dynamics of Machinery",
            "Manufacturing Technology",
            "Heat and Mass Transfer",
        ],
        "CIVIL": [
            "Engineering Geology",
            "Surveying",
            "Mechanics of Solids",
            "Fluid Mechanics",
            "Structural Analysis",
            "Concrete Technology and RCC Structures",
            "Transportation Engineering",
        ],
    }

    def _seed():
        departments = []
        for name, code, description in departments_data:
            department = Department.query.filter_by(code=code).first()
            if department is None:
                department = Department.query.filter_by(name=name).first()
            if department is None:
                department = Department(
                    name=name,
                    code=code,
                    description=description,
                    is_active=True,
                )
                db.session.add(department)
                db.session.flush()
            departments.append(department)

        academic_year = (
            AcademicYear.query.filter_by(is_current=True)
            .order_by(AcademicYear.start_date.desc())
            .first()
        )
        if academic_year is None:
            today = date.today()
            start_year = today.year if today.month >= 6 else today.year - 1
            year_label = f"{start_year}-{start_year + 1}"
            academic_year = AcademicYear.query.filter_by(year_label=year_label).first()
            if academic_year is None:
                academic_year = AcademicYear(
                    year_label=year_label,
                    start_date=date(start_year, 6, 1),
                    end_date=date(start_year + 1, 5, 31),
                    is_current=True,
                )
                db.session.add(academic_year)
                db.session.flush()
            else:
                academic_year.is_current = True

        for department in departments:
            department_semesters = {}
            for semester_number in range(1, 9):
                semester = Semester.query.filter_by(
                    department_id=department.id,
                    academic_year_id=academic_year.id,
                    semester_number=semester_number,
                ).first()
                if semester is None:
                    semester = Semester(
                        semester_number=semester_number,
                        semester_name=f"Semester {semester_number}",
                        academic_year_id=academic_year.id,
                        department_id=department.id,
                        is_current=False,
                    )
                    db.session.add(semester)
                    db.session.flush()
                department_semesters[semester_number] = semester

                for section_name in section_names:
                    exists = ClassSection.query.filter_by(
                        section_name=section_name,
                        department_id=department.id,
                        semester_id=semester.id,
                        academic_year_id=academic_year.id,
                    ).first()
                    if exists is None:
                        db.session.add(ClassSection(
                            section_name=section_name,
                            department_id=department.id,
                            semester_id=semester.id,
                            academic_year_id=academic_year.id,
                            max_students=60,
                        ))

            for index, subject_name in enumerate(
                subjects_by_department.get(department.code, []), start=1
            ):
                subject_code = f"{department.code}{100 + index}"
                if Subject.query.filter_by(code=subject_code).first() is None:
                    db.session.add(Subject(
                        subject_name=subject_name,
                        subject_code=subject_code,
                        department_id=department.id,
                        semester_id=department_semesters[index].id,
                        credits=4,
                        max_internal_marks=40,
                        max_external_marks=60,
                        subject_type="theory",
                        is_active=True,
                    ))

        db.session.commit()
        logger.info("Academic departments, semesters, and sections successfully seeded.")

    if app is not None:
        with app.app_context():
            _seed()
    else:
        _seed()


def create_initial_admin(app=None) -> None:
    """
    Create the initial administrator account from environment variables if not exists.
    """
    from extensions import db
    from models import User, Role

    email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip()
    password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    if not email or "@" not in email:
        raise RuntimeError("Set a valid INITIAL_ADMIN_EMAIL before initializing the database.")
    if len(password) < 12 or password.startswith("REPLACE_WITH"):
        raise RuntimeError("Set a unique INITIAL_ADMIN_PASSWORD of at least 12 characters before initializing the database.")

    def _create():
        if User.query.filter_by(email=email).first():
            logger.info("Initial admin already exists: %s", email)
            return

        admin_role = Role.query.filter_by(role_name="Admin").first()
        if not admin_role:
            logger.error("Admin role not found. Run seed_roles() first.")
            return

        username = email.split("@")[0]
        # Check username uniqueness
        counter = 1
        base_username = username
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1

        admin = User(
            username=username,
            email=email,
            first_name="System",
            last_name="Administrator",
            role_id=admin_role.id,
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        logger.info("Initial admin account created: %s (username: %s)", email, username)

    if app is not None:
        with app.app_context():
            _create()
    else:
        _create()


def check_db_health(app=None) -> dict:
    """Verify that the database is reachable and responsive."""
    from extensions import db

    def _check() -> dict:
        try:
            start = time.perf_counter()
            db.session.execute(text("SELECT 1"))
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "ok",
                "message": "Database connection is healthy.",
                "latency_ms": elapsed_ms,
            }
        except OperationalError as exc:
            return {
                "status": "error",
                "message": f"Database unreachable: {exc.orig}",
                "latency_ms": None,
            }
        except SQLAlchemyError as exc:
            return {
                "status": "error",
                "message": str(exc),
                "latency_ms": None,
            }

    if app is not None:
        with app.app_context():
            return _check()
    return _check()


def bootstrap(config_name: str = "production") -> None:
    """Convenience function for CLI setup."""
    from app import create_app

    application = create_app(config_name)
    init_db(application)
    seed_roles(application)
    seed_academic_structure(application)
    create_initial_admin(application)
    health = check_db_health(application)
    print(f"Bootstrap complete. DB health: {health}")


if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "production")
    bootstrap(env)
