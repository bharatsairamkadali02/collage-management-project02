"""
Faculty routes for the College Management System.
All routes require authentication + faculty role.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app, abort
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models import (
    User, Student, Faculty, Subject, ClassSection, FacultyAssignment, Department,
    Attendance, AttendanceSession, Exam, ExamQuestion, ExamOption,
    ExamAttempt, Result, StudyMaterial, Assignment, Notification,
    Semester, AcademicYear
)
from security.decorators import admin_required, faculty_required, student_required, permission_required
from security.permissions import MARK_ATTENDANCE, MANAGE_EXAMS
import datetime
import json
import uuid
from services.s3_service import S3Service
from werkzeug.utils import secure_filename

faculty_bp = Blueprint('faculty', __name__, url_prefix='/faculty')


def _get_current_faculty():
    """Return the Faculty record for the currently logged-in user, or 404."""
    faculty = Faculty.query.filter_by(user_id=current_user.id).first()
    if faculty is None:
        abort(404)
    return faculty


def _s3_client():
    """Use the instance profile in AWS, or configured credentials locally."""
    return S3Service().client


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@faculty_bp.route('/dashboard')
@login_required
@faculty_required
def dashboard():
    faculty = _get_current_faculty()

    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    class_ids = list({a.class_section_id for a in assignments})
    subject_ids = list({a.subject_id for a in assignments})

    assigned_students = (
        Student.query
        .filter(Student.class_section_id.in_(class_ids), Student.academic_status == 'active')
        .count()
    ) if class_ids else 0

    today = datetime.date.today()
    today_sessions = (
        AttendanceSession.query
        .filter(
            AttendanceSession.faculty_id == faculty.id,
            AttendanceSession.session_date == today,
        )
        .count()
    )

    upcoming_exams = (
        Exam.query
        .filter(
            Exam.created_by_faculty_id == faculty.id,
            Exam.exam_date >= today,
            Exam.status == 'published',
        )
        .order_by(Exam.exam_date.asc())
        .limit(5)
        .all()
    )

    return render_template(
        'faculty/dashboard.html',
        stats={
            "total_students": assigned_students,
            "assigned_subjects": len(subject_ids),
            "today_classes": today_sessions,
            "pending_assignments": Assignment.query.filter_by(
                faculty_id=faculty.id, status="draft"
            ).count(),
        },
        faculty=faculty,
        assigned_students=assigned_students,
        assigned_subjects=len(subject_ids),
        today_attendance_sessions=today_sessions,
        upcoming_exams=upcoming_exams,
    )


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------
@faculty_bp.route('/students')
@login_required
@faculty_required
def students():
    faculty = _get_current_faculty()
    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    class_ids = list({a.class_section_id for a in assignments})

    search = request.args.get('search', '').strip()
    query = Student.query.join(User).filter(Student.academic_status == 'active')

    if class_ids:
        query = query.filter(Student.current_class_section_id.in_(class_ids))

    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                Student.enrollment_number.ilike(like),
                Student.student_roll_number.ilike(like),
            )
        )

    students_list = query.order_by(User.last_name).all()
    assigned_sections = (
        ClassSection.query.filter(ClassSection.id.in_(class_ids)).order_by(ClassSection.section_name).all()
        if class_ids else ClassSection.query.order_by(ClassSection.section_name).all()
    )
    return render_template(
        'faculty/students.html',
        students=students_list,
        faculty=faculty,
        assigned_sections=assigned_sections,
    )


@faculty_bp.route('/students/<int:student_id>')
@login_required
@faculty_required
def student_details(student_id):
    faculty = _get_current_faculty()
    student = Student.query.get_or_404(student_id)

    # Soft authorization: only block if faculty HAS assignments but none match
    # this student's section. If faculty has NO assignments at all, allow access.
    faculty_assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    if faculty_assignments:
        class_ids = {a.class_section_id for a in faculty_assignments}
        if student.current_class_section_id not in class_ids:
            abort(403)

    # Build per-subject attendance summary
    att_records = Attendance.query.filter_by(student_id=student_id).all()
    subjects_map = {}
    for r in att_records:
        sub = r.session.subject if hasattr(r, 'session') and r.session else None
        if not sub:
            continue
        sid = sub.id
        if sid not in subjects_map:
            subjects_map[sid] = {'name': sub.subject_name or sub.name, 'total': 0, 'present': 0, 'absent': 0, 'late': 0}
        subjects_map[sid]['total'] += 1
        status = (r.status or '').strip().lower()
        if status == 'present':
            subjects_map[sid]['present'] += 1
        elif status == 'absent':
            subjects_map[sid]['absent'] += 1
        elif status in ('late', 'leave'):
            subjects_map[sid]['late'] += 1
    attendance_subjects = list(subjects_map.values())

    results = Result.query.filter_by(student_id=student_id).all()
    exam_attempts = ExamAttempt.query.filter_by(student_id=student_id).order_by(ExamAttempt.created_at.desc()).all()

    overall_pct = 0
    if att_records:
        try:
            overall_pct = student.get_attendance_percentage()
        except Exception:
            total = sum(s['total'] for s in attendance_subjects)
            present = sum(s['present'] for s in attendance_subjects)
            overall_pct = round((present / total) * 100, 1) if total else 0

    return render_template(
        'faculty/student_details.html',
        student=student,
        results=results,
        exam_attempts=exam_attempts,
        attendance_subjects=attendance_subjects,
        overall_pct=overall_pct,
    )


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
@faculty_bp.route('/attendance')
@login_required
@faculty_required
def attendance():
    faculty = _get_current_faculty()
    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()

    departments = Department.query.filter_by(is_active=True).order_by(Department.department_name.asc()).all()
    all_sections = (
        ClassSection.query
        .join(Semester, ClassSection.semester_id == Semester.id)
        .order_by(ClassSection.section_name.asc())
        .all()
    )
    all_subjects = (
        Subject.query
        .filter_by(is_active=True)
        .join(Semester, Subject.semester_id == Semester.id)
        .order_by(Subject.subject_name.asc())
        .all()
    )

    today = datetime.date.today().isoformat()
    recent_sessions = (
        AttendanceSession.query
        .filter_by(faculty_id=faculty.id)
        .order_by(AttendanceSession.session_date.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'faculty/attendance.html',
        faculty=faculty,
        assignments=assignments,
        departments=departments,
        all_sections=all_sections,
        all_subjects=all_subjects,
        today=today,
        recent_sessions=recent_sessions,
    )


@faculty_bp.route('/api/attendance-session')
@faculty_bp.route('/api/students')
@login_required
@faculty_required
def api_attendance_session():
    faculty = _get_current_faculty()
    subject_id = request.args.get('subject_id') or request.args.get('subject')
    class_section_id = request.args.get('class_section_id') or request.args.get('section')
    date_str = request.args.get('date', datetime.date.today().isoformat())
    session_type = request.args.get('session_type', 'lecture')

    try:
        subject_id = int(subject_id)
        class_section_id = int(class_section_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'subject_id and class_section_id must be valid numbers.'}), 400

    assignment = FacultyAssignment.query.filter_by(
        faculty_id=faculty.id,
        subject_id=subject_id,
        class_section_id=class_section_id,
    ).first()

    faculty_has_assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).first() is not None
    if faculty_has_assignments and not assignment:
        return jsonify({'error': 'You are not assigned to this subject/class combination.'}), 403

    try:
        session_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        session_date = datetime.date.today()

    class_section = ClassSection.query.get_or_404(class_section_id)
    att_session = AttendanceSession.query.filter_by(
        subject_id=subject_id,
        class_section_id=class_section_id,
        session_date=session_date,
        session_type=session_type,
    ).first()

    if not att_session:
        academic_year_id = assignment.academic_year_id if assignment else class_section.academic_year_id
        att_session = AttendanceSession(
            faculty_id=faculty.id,
            subject_id=subject_id,
            class_section_id=class_section_id,
            session_date=session_date,
            session_type=session_type,
            academic_year_id=academic_year_id,
            semester_id=class_section.semester_id,
        )
        db.session.add(att_session)
        db.session.commit()

    # Query active students in this class section
    students = (
        Student.query
        .join(User)
        .filter(
            Student.current_class_section_id == class_section_id,
            Student.academic_status == 'active',
        )
        .order_by(Student.student_roll_number.asc(), User.first_name.asc())
        .all()
    )

    records_map = {
        r.student_id: r.status
        for r in Attendance.query.filter_by(session_id=att_session.id).all()
    }

    return jsonify({
        'session_id': att_session.id,
        'date': session_date.isoformat(),
        'subject_id': subject_id,
        'class_section_id': class_section_id,
        'students': [
            {
                'id': s.id,
                'student_id': s.id,
                'name': f"{s.user.first_name} {s.user.last_name}" if s.user else "Student",
                'roll': s.student_roll_number or s.registration_number or "N/A",
                'enrollment_number': s.student_roll_number or s.registration_number or "N/A",
                'status': records_map.get(s.id, 'present'),
            }
            for s in students
        ],
    }), 200


@faculty_bp.route('/api/attendance/mark', methods=['POST'])
@login_required
@faculty_required
def api_mark_attendance():
    faculty = _get_current_faculty()
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    records = data.get('records', [])

    if not session_id or not isinstance(records, list):
        return jsonify({'error': 'session_id and records[] are required.'}), 400

    att_session = AttendanceSession.query.get_or_404(session_id)
    if att_session.faculty_id != faculty.id:
        att_session.faculty_id = faculty.id

    updated = 0
    for rec in records:
        student_id = rec.get('student_id')
        status = str(rec.get('status', 'Absent')).title()
        if not student_id:
            continue
        student = Student.query.filter_by(
            id=student_id, current_class_section_id=att_session.class_section_id
        ).first()
        if not student or status not in {'Present', 'Absent', 'Late', 'Leave'}:
            continue

        existing = Attendance.query.filter_by(
            session_id=session_id,
            student_id=student_id,
        ).first()

        if existing:
            existing.status = status
            existing.marked_by_faculty_id = faculty.id
        else:
            attendance_record = Attendance(
                session_id=session_id,
                student_id=student_id,
                marked_by_faculty_id=faculty.id,
                status=status,
            )
            db.session.add(attendance_record)
        updated += 1

    db.session.commit()
    return jsonify({'success': True, 'message': f'Attendance marked for {updated} student(s).'}), 200


@faculty_bp.route('/api/attendance-report')
@login_required
@faculty_required
def api_attendance_report():
    """
    GET /faculty/api/attendance-report?subject_id=&class_section_id=

    Returns per-student attendance percentages.
    """
    faculty = _get_current_faculty()
    subject_id = request.args.get('subject_id', type=int)
    class_section_id = request.args.get('class_section_id', type=int)

    if not subject_id or not class_section_id:
        return jsonify({'error': 'subject_id and class_section_id are required.'}), 400

    total_sessions = AttendanceSession.query.filter_by(
        faculty_id=faculty.id,
        subject_id=subject_id,
        class_section_id=class_section_id,
    ).count()

    students = (
        Student.query
        .join(User)
        .filter(
            Student.class_section_id == class_section_id,
            Student.academic_status == 'active',
        )
        .all()
    )

    report = []
    for s in students:
        present_count = (
            Attendance.query.join(AttendanceSession)
            .filter(
                Attendance.student_id == s.id,
                AttendanceSession.subject_id == subject_id,
                AttendanceSession.class_section_id == class_section_id,
                Attendance.status == 'Present',
            )
            .count()
        )
        percentage = round((present_count / total_sessions * 100), 2) if total_sessions else 0
        report.append({
            'student_id': s.id,
            'name': f'{s.user.first_name} {s.user.last_name}',
            'enrollment_number': s.enrollment_number,
            'present_classes': present_count,
            'total_classes': total_sessions,
            'attendance_percentage': percentage,
        })

    return jsonify({'report': report, 'total_sessions': total_sessions}), 200


# ---------------------------------------------------------------------------
# Examinations
# ---------------------------------------------------------------------------
@faculty_bp.route('/examinations')
@login_required
@faculty_required
def examinations():
    faculty = _get_current_faculty()

    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    if assignments:
        assigned_subjects = Subject.query.filter(
            Subject.id.in_([a.subject_id for a in assignments]),
            Subject.is_active == True
        ).order_by(Subject.subject_name).all()
        assigned_sections = ClassSection.query.filter(
            ClassSection.id.in_([a.class_section_id for a in assignments])
        ).order_by(ClassSection.section_name).all()
    else:
        assigned_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_name).all()
        assigned_sections = ClassSection.query.order_by(ClassSection.section_name).all()

    query = Exam.query.filter_by(created_by_faculty_id=faculty.id)

    subject_filter = request.args.get('subject', type=int)
    section_filter = request.args.get('section', type=int)
    status_filter = request.args.get('status', '').strip()

    if subject_filter:
        query = query.filter(Exam.subject_id == subject_filter)
    if section_filter:
        query = query.filter(Exam.class_section_id == section_filter)
    if status_filter:
        query = query.filter(Exam.status == status_filter)

    exams = query.order_by(Exam.start_time.desc()).all()

    return render_template(
        'faculty/examinations.html',
        exams=exams,
        assigned_subjects=assigned_subjects,
        assigned_sections=assigned_sections,
    )


@faculty_bp.route('/examinations/create', methods=['GET', 'POST'])
@login_required
@faculty_required
def create_exam():
    faculty = _get_current_faculty()
    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    has_assignments = len(assignments) > 0

    # ----- Build cascading data -----
    # Allowed subjects: only assigned ones, else all active
    if has_assignments:
        subject_ids = {a.subject_id for a in assignments}
        section_ids = {a.class_section_id for a in assignments}
        allowed_subjects = Subject.query.filter(Subject.id.in_(subject_ids), Subject.is_active == True).all()
        allowed_sections = (
            ClassSection.query
            .filter(ClassSection.id.in_(section_ids))
            .all()
        )
    else:
        allowed_subjects = Subject.query.filter_by(is_active=True).all()
        allowed_sections = ClassSection.query.all()

    # Build dept list (from allowed subjects)
    dept_ids_from_subjects = {s.department_id for s in allowed_subjects}
    departments = Department.query.filter(Department.id.in_(dept_ids_from_subjects)).order_by(Department.department_name).all()

    # Semester numbers available (1-8)
    sem_numbers = sorted({s.semester.semester_number for s in allowed_subjects if s.semester})

    # subjects_data: {dept_id: {sem_number: [{id, name, code}]}}
    subjects_data = {}
    for sub in allowed_subjects:
        if not sub.semester:
            continue
        dk = str(sub.department_id)
        sk = str(sub.semester.semester_number)
        subjects_data.setdefault(dk, {}).setdefault(sk, []).append({
            'id': sub.id,
            'name': sub.subject_name,
            'code': sub.subject_code,
        })

    # sections_data: {dept_id: {sem_number: [{id, name}]}}
    sections_data = {}
    for sec in allowed_sections:
        if not sec.semester or not sec.department_id:
            continue
        dk = str(sec.department_id)
        sk = str(sec.semester.semester_number)
        sections_data.setdefault(dk, {}).setdefault(sk, []).append({
            'id': sec.id,
            'name': sec.section_name,
        })

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        subject_id = request.form.get('subject_id', type=int)
        class_section_id = request.form.get('class_section_id', type=int)
        semester_id = request.form.get('semester_id', type=int)
        academic_year_id = request.form.get('academic_year_id', type=int)
        exam_date = request.form.get('start_time') or request.form.get('exam_date')
        duration_minutes = request.form.get('duration_minutes', 60, type=int)
        total_marks = request.form.get('total_marks', 100, type=int)
        passing_marks = request.form.get('passing_marks', 40, type=int)
        exam_type = request.form.get('exam_type', 'mcq').strip()
        instructions = request.form.get('instructions', '').strip()

        ctx = dict(
            assignments=assignments,
            departments=departments,
            sem_numbers=sem_numbers,
            subjects_data=json.dumps(subjects_data),
            sections_data=json.dumps(sections_data),
            has_assignments=has_assignments,
        )

        if not all([title, subject_id, class_section_id, exam_date]):
            flash('Exam Title, Subject, Class Section, and Start Date/Time are required.', 'danger')
            return render_template('faculty/create_exam.html', **ctx)

        # Soft auth: only enforce if faculty has assignments
        teaching_assignment = FacultyAssignment.query.filter_by(
            faculty_id=faculty.id,
            subject_id=subject_id,
            class_section_id=class_section_id,
        ).first()
        if has_assignments and not teaching_assignment:
            flash('You are not assigned to this subject/class combination.', 'danger')
            return render_template('faculty/create_exam.html', **ctx)

        class_section = ClassSection.query.get_or_404(class_section_id)
        semester_id = semester_id or class_section.semester_id
        if teaching_assignment:
            academic_year_id = academic_year_id or teaching_assignment.academic_year_id
        else:
            # fallback: use current academic year
            current_year = AcademicYear.query.filter_by(is_current=True).first()
            academic_year_id = academic_year_id or (current_year.id if current_year else None)

        exam = Exam(
            title=title,
            subject_id=subject_id,
            class_section_id=class_section_id,
            semester_id=semester_id,
            academic_year_id=academic_year_id,
            created_by_faculty_id=faculty.id,
            start_time=datetime.datetime.fromisoformat(exam_date),
            duration_minutes=duration_minutes,
            total_marks=total_marks,
            passing_marks=passing_marks,
            exam_type=exam_type,
            instructions=instructions,
            status='draft',
        )
        db.session.add(exam)
        db.session.commit()
        flash('Exam created successfully. Add questions now.', 'success')
        return redirect(url_for('faculty.exam_questions', id=exam.id))

    return render_template(
        'faculty/create_exam.html',
        assignments=assignments,
        departments=departments,
        sem_numbers=sem_numbers,
        subjects_data=json.dumps(subjects_data),
        sections_data=json.dumps(sections_data),
        has_assignments=has_assignments,
    )




@faculty_bp.route('/examinations/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@faculty_required
def edit_exam(id):
    faculty = _get_current_faculty()
    exam = Exam.query.get_or_404(id)
    if exam.created_by_faculty_id != faculty.id:
        abort(403)

    data = request.get_json(silent=True) or request.form
    exam.title = (data.get('title') or exam.title).strip()
    if data.get('exam_date'):
        exam.start_time = datetime.datetime.fromisoformat(data.get('exam_date'))
    exam.duration_minutes = int(data.get('duration_minutes', exam.duration_minutes))
    exam.total_marks = int(data.get('total_marks', exam.total_marks))
    exam.passing_marks = int(data.get('passing_marks', exam.passing_marks))
    exam.instructions = (data.get('instructions') or exam.instructions or '').strip()

    db.session.commit()
    return jsonify({'message': 'Exam updated.', 'exam_id': exam.id}), 200


@faculty_bp.route('/examinations/<int:id>/publish', methods=['POST'])
@login_required
@faculty_required
def publish_exam(id):
    faculty = _get_current_faculty()
    exam = Exam.query.get_or_404(id)
    if exam.created_by_faculty_id != faculty.id:
        abort(403)

    question_count = ExamQuestion.query.filter_by(exam_id=id).count()
    if question_count == 0:
        if request.is_json:
            return jsonify({'error': 'Cannot publish an exam with no questions.'}), 400
        flash('Cannot publish an exam with no questions. Please add questions first.', 'warning')
        return redirect(url_for('faculty.exam_questions', id=id))

    exam.status = 'published'
    db.session.commit()
    if request.is_json:
        return jsonify({'message': 'Exam published.'}), 200
    flash('Exam published successfully.', 'success')
    return redirect(url_for('faculty.examinations'))


@faculty_bp.route('/examinations/<int:id>/close', methods=['POST'])
@login_required
@faculty_required
def close_exam(id):
    faculty = _get_current_faculty()
    exam = Exam.query.get_or_404(id)
    if exam.created_by_faculty_id != faculty.id:
        abort(403)
    exam.status = 'closed'
    db.session.commit()
    if request.is_json:
        return jsonify({'message': 'Exam closed.'}), 200
    flash('Exam closed.', 'info')
    return redirect(url_for('faculty.examinations'))


@faculty_bp.route('/examinations/<int:id>/delete', methods=['POST'])
@login_required
@faculty_required
def delete_exam(id):
    faculty = _get_current_faculty()
    exam = Exam.query.get_or_404(id)
    if exam.created_by_faculty_id and exam.created_by_faculty_id != faculty.id:
        abort(403)
    title = exam.title
    db.session.delete(exam)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'message': 'Exam deleted.'}), 200
    flash(f'Examination "{title}" deleted successfully.', 'success')
    return redirect(url_for('faculty.examinations'))


@faculty_bp.route('/examinations/<int:id>/questions')
@login_required
@faculty_required
def exam_questions(id):
    faculty = _get_current_faculty()
    exam = Exam.query.get_or_404(id)
    if exam.created_by_faculty_id != faculty.id:
        abort(403)
    questions = ExamQuestion.query.filter_by(exam_id=id).order_by(ExamQuestion.order_number).all()
    return render_template('faculty/questions.html', exam=exam, questions=questions)


@faculty_bp.route('/examinations/<int:id>/questions/add', methods=['POST'])
@login_required
@faculty_required
def add_question(id):
    faculty = _get_current_faculty()
    exam = Exam.query.get_or_404(id)
    if exam.created_by_faculty_id and exam.created_by_faculty_id != faculty.id:
        abort(403)

    is_json = request.is_json
    if is_json:
        data = request.get_json(silent=True) or {}
        question_text = (data.get('question_text') or '').strip()
        marks = float(data.get('marks', 1))
        options_data = data.get('options', [])
    else:
        question_text = request.form.get('question_text', '').strip()
        marks = float(request.form.get('marks', 1) or 1)
        correct_num = request.form.get('correct_option', '1')
        options_data = []
        for i in range(1, 5):
            opt_val = request.form.get(f'option_{i}', '').strip()
            if opt_val:
                options_data.append({
                    'text': opt_val,
                    'is_correct': (str(i) == str(correct_num)),
                })

    if not question_text:
        if is_json:
            return jsonify({'error': 'question_text is required.'}), 400
        flash('Question text is required.', 'danger')
        return redirect(url_for('faculty.exam_questions', id=id))

    order = ExamQuestion.query.filter_by(exam_id=id).count() + 1
    question = ExamQuestion(
        exam_id=id,
        question_text=question_text,
        marks=marks,
        order_number=order,
    )
    db.session.add(question)
    db.session.flush()

    for opt in options_data:
        option = ExamOption(
            question_id=question.id,
            option_text=opt.get('text', '').strip(),
            is_correct=bool(opt.get('is_correct', False)),
        )
        db.session.add(option)

    db.session.commit()

    if is_json:
        return jsonify({'success': True, 'message': 'Question added.', 'question_id': question.id}), 201
    flash('Question added successfully.', 'success')
    return redirect(url_for('faculty.exam_questions', id=id))


@faculty_bp.route('/questions/<int:id>/edit', methods=['POST'])
@login_required
@faculty_required
def edit_question(id):
    faculty = _get_current_faculty()
    question = ExamQuestion.query.get_or_404(id)
    if question.exam.created_by_faculty_id != faculty.id:
        abort(403)

    data = request.get_json(silent=True) or {}
    question.question_text = (data.get('question_text') or question.question_text).strip()
    question.marks = float(data.get('marks', question.marks))

    db.session.commit()
    return jsonify({'message': 'Question updated.'}), 200


@faculty_bp.route('/questions/<int:id>/delete', methods=['POST'])
@login_required
@faculty_required
def delete_question(id):
    faculty = _get_current_faculty()
    question = ExamQuestion.query.get_or_404(id)
    if question.exam.created_by_faculty_id != faculty.id:
        abort(403)
    db.session.delete(question)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Question deleted.'}), 200


@faculty_bp.route('/examinations/<int:id>/attempts')
@login_required
@faculty_required
def exam_attempts(id):
    faculty = _get_current_faculty()
    exam = Exam.query.get_or_404(id)
    if exam.created_by_faculty_id != faculty.id:
        abort(403)

    attempts = ExamAttempt.query.filter_by(exam_id=id).all()

    if request.headers.get('Accept') == 'application/json':
        return jsonify([
            {
                'attempt_id': a.id,
                'student_id': a.student_id,
                'score': a.score,
                'total': a.total_marks,
                'percentage': a.percentage,
                'submitted_at': a.submitted_at.isoformat() if a.submitted_at else None,
                'status': a.status,
            }
            for a in attempts
        ]), 200

    return render_template('faculty/exam_attempts.html', exam=exam, attempts=attempts)


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------
@faculty_bp.route('/marks')
@login_required
@faculty_required
def marks():
    faculty = _get_current_faculty()
    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    semesters = Semester.query.order_by(Semester.name).all()
    return render_template('faculty/marks.html', faculty=faculty, assignments=assignments, semesters=semesters)


@faculty_bp.route('/marks/add', methods=['POST'])
@login_required
@faculty_required
def add_marks():
    """
    Body: {student_id, subject_id, semester_id, academic_year_id,
           internal_marks, external_marks, practical_marks}
    """
    faculty = _get_current_faculty()
    data = request.get_json(silent=True) or request.form

    student_id = int(data.get('student_id', 0))
    subject_id = int(data.get('subject_id', 0))
    semester_id = int(data.get('semester_id', 0))
    academic_year_id = int(data.get('academic_year_id', 0))
    internal_marks = float(data.get('internal_marks', 0))
    external_marks = float(data.get('external_marks', 0))
    practical_marks = float(data.get('practical_marks', 0))

    if not all([student_id, subject_id, semester_id, academic_year_id]):
        return jsonify({'error': 'student_id, subject_id, semester_id, and academic_year_id are required.'}), 400

    result = Result.query.filter_by(
        student_id=student_id,
        subject_id=subject_id,
        semester_id=semester_id,
        academic_year_id=academic_year_id,
    ).first()

    if result:
        result.internal_marks = internal_marks
        result.external_marks = external_marks
        result.practical_marks = practical_marks
        result.total_marks = internal_marks + external_marks + practical_marks
        result.marked_by_id = faculty.id
        result.updated_at = datetime.datetime.utcnow()
    else:
        result = Result(
            student_id=student_id,
            subject_id=subject_id,
            semester_id=semester_id,
            academic_year_id=academic_year_id,
            internal_marks=internal_marks,
            external_marks=external_marks,
            practical_marks=practical_marks,
            total_marks=internal_marks + external_marks + practical_marks,
            marked_by_id=faculty.id,
            is_published=False,
        )
        db.session.add(result)

    db.session.commit()
    return jsonify({'message': 'Marks saved.', 'result_id': result.id}), 200


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@faculty_bp.route('/results')
@login_required
@faculty_required
def results():
    faculty = _get_current_faculty()
    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    semesters = Semester.query.order_by(Semester.name).all()
    return render_template('faculty/results.html', faculty=faculty, assignments=assignments, semesters=semesters)


@faculty_bp.route('/results/publish', methods=['POST'])
@login_required
@faculty_required
def publish_results():
    """Body: {subject_id, semester_id, academic_year_id}"""
    faculty = _get_current_faculty()
    data = request.get_json(silent=True) or {}
    subject_id = int(data.get('subject_id', 0))
    semester_id = int(data.get('semester_id', 0))
    academic_year_id = int(data.get('academic_year_id', 0))

    if not all([subject_id, semester_id, academic_year_id]):
        return jsonify({'error': 'subject_id, semester_id, and academic_year_id are required.'}), 400

    updated = (
        Result.query
        .filter_by(
            subject_id=subject_id,
            semester_id=semester_id,
            academic_year_id=academic_year_id,
            marked_by_id=faculty.id,
        )
        .update({'is_published': True, 'published_at': datetime.datetime.utcnow()})
    )
    db.session.commit()
    return jsonify({'message': f'{updated} result(s) published.'}), 200


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
@faculty_bp.route('/assignments')
@login_required
@faculty_required
def assignments():
    faculty = _get_current_faculty()
    all_assignments = (
        Assignment.query
        .filter_by(faculty_id=faculty.id)
        .order_by(Assignment.due_date.asc())
        .all()
    )
    return render_template('faculty/assignments.html', assignments=all_assignments)


@faculty_bp.route('/assignments/create', methods=['POST'])
@login_required
@faculty_required
def create_assignment():
    faculty = _get_current_faculty()
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    subject_id = request.form.get('subject_id', type=int)
    class_section_id = request.form.get('class_section_id', type=int)
    due_date = request.form.get('due_date')
    max_marks = request.form.get('max_marks', 100, type=int)

    if not all([title, subject_id, class_section_id, due_date]):
        flash('Title, subject, class, and due date are required.', 'danger')
        return redirect(url_for('faculty.assignments'))

    file_key = None
    file_name = None
    file_size = None
    file = request.files.get('file')
    if file and file.filename:
        s3 = S3Service()
        file_name = secure_filename(file.filename)
        file_size = request.content_length
        key = f"assignments/{faculty.id}/{uuid.uuid4().hex}_{file_name}"
        file_key = s3.upload_file(file, key, content_type=file.content_type)
        if not file_key:
            flash('File upload failed. Please try again.', 'danger')
            return redirect(url_for('faculty.assignments'))

    assignment = Assignment(
        title=title,
        description=description,
        subject_id=subject_id,
        class_section_id=class_section_id,
        faculty_id=faculty.id,
        due_date=datetime.datetime.fromisoformat(due_date),
        max_marks=max_marks,
        file_key=file_key,
        file_name=file_name,
        file_size=file_size,
    )
    db.session.add(assignment)
    db.session.commit()
    flash('Assignment created successfully.', 'success')
    return redirect(url_for('faculty.assignments'))


# ---------------------------------------------------------------------------
# Study Materials
# ---------------------------------------------------------------------------
@faculty_bp.route('/materials')
@login_required
@faculty_required
def materials():
    faculty = _get_current_faculty()
    all_materials = (
        StudyMaterial.query
        .filter_by(faculty_id=faculty.id)
        .order_by(StudyMaterial.created_at.desc())
        .all()
    )
    return render_template('faculty/materials.html', materials=all_materials)


@faculty_bp.route('/materials/upload', methods=['POST'])
@login_required
@faculty_required
def upload_material():
    faculty = _get_current_faculty()
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    subject_id = request.form.get('subject_id', type=int)
    class_section_id = request.form.get('class_section_id', type=int)
    file = request.files.get('file')

    if not title or not subject_id or not file or not file.filename:
        return jsonify({'error': 'title, subject_id, and file are required.'}), 400

    s3 = S3Service()
    filename = secure_filename(file.filename)
    key = f'materials/{faculty.id}/{datetime.datetime.utcnow().timestamp()}_{filename}'
    file_size = request.content_length
    if not s3.upload_file(file, key, content_type=file.content_type):
        return jsonify({'error': 'File upload failed.'}), 500

    material = StudyMaterial(
        title=title,
        description=description,
        subject_id=subject_id,
        class_section_id=class_section_id,
        faculty_id=faculty.id,
        file_key=key,
        file_name=filename,
        file_size=file_size,
        file_type=file.content_type,
    )
    db.session.add(material)
    db.session.commit()
    return jsonify({'message': 'Material uploaded.', 'material_id': material.id}), 201


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@faculty_bp.route('/notifications')
@login_required
@faculty_required
def notifications():
    page = request.args.get('page', 1, type=int)
    faculty = _get_current_faculty()
    all_notifications = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .paginate(page=page, per_page=25)
    )
    return render_template('faculty/notifications.html', notifications=all_notifications)


@faculty_bp.route('/notifications/send', methods=['POST'])
@login_required
@faculty_required
def send_notification():
    faculty = _get_current_faculty()
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    message = (data.get('message') or '').strip()
    class_section_id = data.get('class_section_id', type=int) if hasattr(data, 'get') else data.get('class_section_id')

    if not title or not message:
        return jsonify({'error': 'title and message are required.'}), 400

    students = Student.query.filter_by(
        class_section_id=int(class_section_id) if class_section_id else None,
        academic_status='active',
    ).all() if class_section_id else []

    count = 0
    for student in students:
        notif = Notification(
            user_id=student.user_id,
            title=title,
            message=message,
            sent_by_id=current_user.id,
            is_read=False,
        )
        db.session.add(notif)
        count += 1

    db.session.commit()
    return jsonify({'message': f'Notification sent to {count} student(s).'}), 201


# ---------------------------------------------------------------------------
# API – Faculty's classes and subjects
# ---------------------------------------------------------------------------
@faculty_bp.route('/api/my-classes')
@login_required
@faculty_required
def api_my_classes():
    faculty = _get_current_faculty()
    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    class_ids = list({a.class_section_id for a in assignments})
    sections = ClassSection.query.filter(ClassSection.id.in_(class_ids)).all()
    return jsonify([
        {'id': s.id, 'name': s.name, 'department': s.department.name if s.department else None}
        for s in sections
    ]), 200


@faculty_bp.route('/api/my-subjects')
@login_required
@faculty_required
def api_my_subjects():
    faculty = _get_current_faculty()
    assignments = FacultyAssignment.query.filter_by(faculty_id=faculty.id).all()
    subject_ids = list({a.subject_id for a in assignments})
    subjects = Subject.query.filter(Subject.id.in_(subject_ids)).all()
    return jsonify([
        {'id': s.id, 'name': s.name, 'code': s.code, 'credits': s.credits}
        for s in subjects
    ]), 200
