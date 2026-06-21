import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

from models import db, User, CareerProfile, Profession, CareerRecommendation
from models import ConsultationRequest, WorkTask, PublishedMaterial, SystemLog, ChatMessage
from auth import role_required
from ai_service import get_career_recommendation, is_gemini_configured, get_chat_response

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'career-ai-hub-secret-2024')


def get_database_uri():
    """Render PostgreSQL немесе жергілікті SQLite."""
    url = os.environ.get('DATABASE_URL')
    if url:
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url
    instance_dir = os.environ.get(
        'INSTANCE_PATH',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance'),
    )
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, 'career.db')
    return 'sqlite:///' + db_path.replace('\\', '/')


app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Жүйеге кіріңіз.'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_ai_status():
    return {
        'ai_gemini_enabled': is_gemini_configured(),
    }


def log_action(action, details=''):
    entry = SystemLog(user_id=current_user.id if current_user.is_authenticated else None,
                      action=action, details=details)
    db.session.add(entry)
    db.session.commit()


def dashboard_redirect():
    role_map = {
        'admin': 'admin_dashboard',
        'manager': 'manager_dashboard',
        'employee': 'employee_dashboard',
        'moderator': 'moderator_dashboard',
        'user': 'user_dashboard',
    }
    return redirect(url_for(role_map.get(current_user.role, 'user_dashboard')))


# ─── Public ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    professions = Profession.query.filter_by(is_published=True).limit(6).all()
    return render_template('index.html', professions=professions)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return dashboard_redirect()
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        if not email or not password or not full_name:
            flash('Барлық өрістерді толтырыңыз.', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Бұл email тіркелген.', 'error')
            return render_template('register.html')
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            full_name=full_name,
            role='user',
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(CareerProfile(user_id=user.id))
        db.session.commit()
        flash('Тіркелу сәтті! Кіріңіз.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return dashboard_redirect()
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password) and user.is_active:
            login_user(user)
            log_action('login', email)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return dashboard_redirect()
        flash('Email немесе пароль дұрыс емес.', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    log_action('logout')
    logout_user()
    flash('Сіз жүйеден шықтыңыз.', 'success')
    return redirect(url_for('index'))


@app.route('/professions')
def professions_list():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    query = Profession.query.filter_by(is_published=True)
    if q:
        query = query.filter(
            db.or_(Profession.title.ilike(f'%{q}%'), Profession.description.ilike(f'%{q}%'))
        )
    if category:
        query = query.filter_by(category=category)
    professions = query.order_by(Profession.title).all()
    categories = db.session.query(Profession.category).filter(
        Profession.is_published == True, Profession.category.isnot(None)
    ).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    return render_template('professions.html', professions=professions,
                           q=q, category=category, categories=categories)


# ─── Admin ────────────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    stats = {
        'users': User.query.count(),
        'professions': Profession.query.count(),
        'requests': ConsultationRequest.query.count(),
        'materials': PublishedMaterial.query.filter_by(status='pending').count(),
    }
    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, logs=logs)


@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    q = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '')
    query = User.query
    if q:
        query = query.filter(db.or_(User.full_name.ilike(f'%{q}%'), User.email.ilike(f'%{q}%')))
    if role_filter:
        query = query.filter_by(role=role_filter)
    users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, q=q, role_filter=role_filter)


@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_user_create():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'user')
        if role not in ('admin', 'manager', 'employee', 'moderator', 'user'):
            role = 'user'
        if User.query.filter_by(email=email).first():
            flash('Email бар.', 'error')
        else:
            user = User(email=email, password_hash=generate_password_hash(password),
                        full_name=full_name, role=role)
            db.session.add(user)
            db.session.flush()
            db.session.add(CareerProfile(user_id=user.id))
            db.session.commit()
            log_action('user_create', f'{email} ({role})')
            flash('Пайдаланушы қосылды.', 'success')
            return redirect(url_for('admin_users'))
    return render_template('admin/user_form.html', user=None)


@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_user_edit(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', user.full_name)
        user.role = request.form.get('role', user.role)
        user.is_active = request.form.get('is_active') == 'on'
        user.phone = request.form.get('phone', '')
        new_pass = request.form.get('password', '')
        if new_pass:
            user.password_hash = generate_password_hash(new_pass)
        db.session.commit()
        log_action('user_edit', user.email)
        flash('Жаңартылды.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin/user_form.html', user=user)


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Өзіңізді жоя алмайсыз.', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        log_action('user_delete', user.email)
        flash('Жойылды.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/professions')
@login_required
@role_required('admin')
def admin_professions():
    q = request.args.get('q', '').strip()
    query = Profession.query
    if q:
        query = query.filter(Profession.title.ilike(f'%{q}%'))
    professions = query.order_by(Profession.title).all()
    return render_template('admin/professions.html', professions=professions, q=q)


@app.route('/admin/professions/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_profession_create():
    if request.method == 'POST':
        prof = Profession(
            title=request.form.get('title', ''),
            description=request.form.get('description', ''),
            category=request.form.get('category', ''),
            salary_min=int(request.form.get('salary_min') or 0),
            salary_max=int(request.form.get('salary_max') or 0),
            skills_required=request.form.get('skills_required', ''),
            growth_outlook=request.form.get('growth_outlook', ''),
            is_published=request.form.get('is_published') == 'on',
        )
        db.session.add(prof)
        db.session.commit()
        log_action('profession_create', prof.title)
        flash('Мамандық қосылды.', 'success')
        return redirect(url_for('admin_professions'))
    return render_template('admin/profession_form.html', profession=None)


@app.route('/admin/professions/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_profession_edit(pid):
    profession = Profession.query.get_or_404(pid)
    if request.method == 'POST':
        profession.title = request.form.get('title', profession.title)
        profession.description = request.form.get('description', '')
        profession.category = request.form.get('category', '')
        profession.salary_min = int(request.form.get('salary_min') or 0)
        profession.salary_max = int(request.form.get('salary_max') or 0)
        profession.skills_required = request.form.get('skills_required', '')
        profession.growth_outlook = request.form.get('growth_outlook', '')
        profession.is_published = request.form.get('is_published') == 'on'
        db.session.commit()
        flash('Сақталды.', 'success')
        return redirect(url_for('admin_professions'))
    return render_template('admin/profession_form.html', profession=profession)


@app.route('/admin/professions/<int:pid>/delete', methods=['POST'])
@login_required
@role_required('admin')
def admin_profession_delete(pid):
    prof = Profession.query.get_or_404(pid)
    db.session.delete(prof)
    db.session.commit()
    flash('Жойылды.', 'success')
    return redirect(url_for('admin_professions'))


@app.route('/admin/logs')
@login_required
@role_required('admin')
def admin_logs():
    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(100).all()
    return render_template('admin/logs.html', logs=logs)


# ─── Manager ──────────────────────────────────────────────────────────────────

@app.route('/manager')
@login_required
@role_required('manager')
def manager_dashboard():
    requests_list = ConsultationRequest.query.order_by(
        ConsultationRequest.created_at.desc()
    ).limit(20).all()
    stats = {
        'new': ConsultationRequest.query.filter_by(status='new').count(),
        'in_progress': ConsultationRequest.query.filter_by(status='in_progress').count(),
        'done': ConsultationRequest.query.filter_by(status='done').count(),
    }
    return render_template('manager/dashboard.html', requests=requests_list, stats=stats)


@app.route('/manager/requests')
@login_required
@role_required('manager')
def manager_requests():
    status = request.args.get('status', '')
    q = request.args.get('q', '').strip()
    query = ConsultationRequest.query
    if status:
        query = query.filter_by(status=status)
    if q:
        query = query.filter(ConsultationRequest.subject.ilike(f'%{q}%'))
    requests_list = query.order_by(ConsultationRequest.created_at.desc()).all()
    return render_template('manager/requests.html', requests=requests_list,
                           status=status, q=q)


@app.route('/manager/requests/<int:rid>', methods=['GET', 'POST'])
@login_required
@role_required('manager')
def manager_request_detail(rid):
    req = ConsultationRequest.query.get_or_404(rid)
    employees = User.query.filter_by(role='employee', is_active=True).all()
    if request.method == 'POST':
        req.status = request.form.get('status', req.status)
        req.manager_id = current_user.id
        db.session.commit()
        emp_id = request.form.get('employee_id')
        if emp_id and request.form.get('assign_task'):
            task = WorkTask(
                title=f'Консультация: {req.subject}',
                description=req.message,
                employee_id=int(emp_id),
                request_id=req.id,
                status='assigned',
            )
            db.session.add(task)
            req.status = 'in_progress'
            db.session.commit()
        log_action('request_update', f'#{req.id} -> {req.status}')
        flash('Жаңартылды.', 'success')
        return redirect(url_for('manager_requests'))
    return render_template('manager/request_detail.html', req=req, employees=employees)


# ─── Employee ─────────────────────────────────────────────────────────────────

@app.route('/employee')
@login_required
@role_required('employee')
def employee_dashboard():
    tasks = WorkTask.query.filter_by(employee_id=current_user.id).order_by(
        WorkTask.created_at.desc()
    ).all()
    return render_template('employee/dashboard.html', tasks=tasks)


@app.route('/employee/tasks/<int:tid>', methods=['GET', 'POST'])
@login_required
@role_required('employee')
def employee_task_detail(tid):
    task = WorkTask.query.get_or_404(tid)
    if task.employee_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        task.status = request.form.get('status', task.status)
        db.session.commit()
        log_action('task_update', f'#{task.id}')
        flash('Статус жаңартылды.', 'success')
        return redirect(url_for('employee_dashboard'))
    return render_template('employee/task_detail.html', task=task)


# ─── Moderator ────────────────────────────────────────────────────────────────

@app.route('/moderator')
@login_required
@role_required('moderator')
def moderator_dashboard():
    pending_materials = PublishedMaterial.query.filter_by(status='pending').all()
    pending_recs = CareerRecommendation.query.filter_by(status='pending').all()
    return render_template('moderator/dashboard.html',
                           materials=pending_materials, recommendations=pending_recs)


@app.route('/moderator/materials')
@login_required
@role_required('moderator')
def moderator_materials():
    status = request.args.get('status', 'pending')
    materials = PublishedMaterial.query.filter_by(status=status).order_by(
        PublishedMaterial.created_at.desc()
    ).all()
    return render_template('moderator/materials.html', materials=materials, status=status)


@app.route('/moderator/materials/<int:mid>/review', methods=['POST'])
@login_required
@role_required('moderator')
def moderator_material_review(mid):
    mat = PublishedMaterial.query.get_or_404(mid)
    mat.status = request.form.get('status', 'approved')
    mat.reviewed_by = current_user.id
    db.session.commit()
    log_action('material_review', f'#{mid} -> {mat.status}')
    flash('Материал тексерілді.', 'success')
    return redirect(url_for('moderator_materials'))


@app.route('/moderator/recommendations')
@login_required
@role_required('moderator')
def moderator_recommendations():
    recs = CareerRecommendation.query.filter_by(status='pending').order_by(
        CareerRecommendation.created_at.desc()
    ).all()
    return render_template('moderator/recommendations.html', recommendations=recs)


@app.route('/moderator/recommendations/<int:rid>/review', methods=['POST'])
@login_required
@role_required('moderator')
def moderator_rec_review(rid):
    rec = CareerRecommendation.query.get_or_404(rid)
    rec.status = request.form.get('status', 'approved')
    rec.reviewed_by = current_user.id
    db.session.commit()
    flash('Ұсыныс тексерілді.', 'success')
    return redirect(url_for('moderator_recommendations'))


# ─── User / Client ────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
@role_required('user')
def user_dashboard():
    profile = CareerProfile.query.filter_by(user_id=current_user.id).first()
    recommendations = CareerRecommendation.query.filter_by(
        user_id=current_user.id
    ).order_by(CareerRecommendation.created_at.desc()).limit(5).all()
    requests_list = ConsultationRequest.query.filter_by(
        client_id=current_user.id
    ).order_by(ConsultationRequest.created_at.desc()).limit(5).all()
    return render_template('user/dashboard.html', profile=profile,
                           recommendations=recommendations, requests=requests_list)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    prof = CareerProfile.query.filter_by(user_id=current_user.id).first()
    if not prof:
        prof = CareerProfile(user_id=current_user.id)
        db.session.add(prof)
        db.session.commit()
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', current_user.full_name)
        current_user.phone = request.form.get('phone', '')
        prof.interests = request.form.get('interests', '')
        prof.skills = request.form.get('skills', '')
        prof.education = request.form.get('education', '')
        prof.experience_years = int(request.form.get('experience_years') or 0)
        prof.preferred_field = request.form.get('preferred_field', '')
        db.session.commit()
        flash('Профиль сақталды.', 'success')
        if current_user.role != 'user':
            return dashboard_redirect()
        return redirect(url_for('profile'))
    return render_template('user/profile.html', profile=prof)


@app.route('/recommend', methods=['GET', 'POST'])
@login_required
@role_required('user')
def recommend():
    professions = Profession.query.filter_by(is_published=True).all()
    if request.method == 'POST':
        prof_id = int(request.form.get('profession_id', 0))
        profession = Profession.query.get_or_404(prof_id)
        profile = CareerProfile.query.filter_by(user_id=current_user.id).first()
        score, summary, source = get_career_recommendation(profession, profile)
        rec = CareerRecommendation(
            user_id=current_user.id,
            profession_id=profession.id,
            match_score=score,
            ai_summary=summary,
            status='pending',
        )
        db.session.add(rec)
        db.session.commit()
        log_action('ai_recommendation', f'{profession.title} ({source})')
        ai_label = 'Google Gemini AI' if source == 'gemini' else 'Жергілікті AI (Gemini quota/limit)'
        flash(f'{ai_label} ұсынысы дайын! Сәйкестік: {score}%', 'success')
        return redirect(url_for('user_recommendations'))
    return render_template('user/recommend.html', professions=professions)


@app.route('/my-recommendations')
@login_required
@role_required('user')
def user_recommendations():
    recs = CareerRecommendation.query.filter_by(user_id=current_user.id).order_by(
        CareerRecommendation.created_at.desc()
    ).all()
    return render_template('user/recommendations.html', recommendations=recs)


@app.route('/request-consultation', methods=['GET', 'POST'])
@login_required
@role_required('user')
def request_consultation():
    if request.method == 'POST':
        req = ConsultationRequest(
            client_id=current_user.id,
            subject=request.form.get('subject', ''),
            message=request.form.get('message', ''),
            status='new',
        )
        db.session.add(req)
        db.session.commit()
        log_action('consultation_request', req.subject)
        flash('Өтінім жіберілді!', 'success')
        return redirect(url_for('user_requests'))
    return render_template('user/request_form.html')


@app.route('/my-requests')
@login_required
@role_required('user')
def user_requests():
    requests_list = ConsultationRequest.query.filter_by(
        client_id=current_user.id
    ).order_by(ConsultationRequest.created_at.desc()).all()
    return render_template('user/requests.html', requests=requests_list)


@app.route('/materials/new', methods=['GET', 'POST'])
@login_required
@role_required('user')
def user_material_new():
    if request.method == 'POST':
        mat = PublishedMaterial(
            title=request.form.get('title', ''),
            content=request.form.get('content', ''),
            author_id=current_user.id,
            status='pending',
        )
        db.session.add(mat)
        db.session.commit()
        flash('Материал модерацияға жіберілді.', 'success')
        return redirect(url_for('user_dashboard'))
    return render_template('user/material_form.html')


# ─── AI Chat ──────────────────────────────────────────────────────────────────

@app.route('/chat')
@login_required
@role_required('user')
def ai_chat():
    messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(
        ChatMessage.created_at
    ).limit(50).all()
    return render_template('user/chat.html', messages=messages)


@app.route('/api/chat', methods=['POST'])
@login_required
@role_required('user')
def api_chat():
    data = request.get_json(silent=True) or {}
    user_text = (data.get('message') or '').strip()
    if not user_text:
        return jsonify({'success': False, 'error': 'Хабарлама бос'}), 400
    if len(user_text) > 2000:
        return jsonify({'success': False, 'error': 'Хабарлама тым ұзын (max 2000)'}), 400

    profile = CareerProfile.query.filter_by(user_id=current_user.id).first()
    history_rows = ChatMessage.query.filter_by(user_id=current_user.id).order_by(
        ChatMessage.created_at
    ).limit(20).all()
    history = [{'role': m.role, 'content': m.content} for m in history_rows]

    user_msg = ChatMessage(user_id=current_user.id, role='user', content=user_text)
    db.session.add(user_msg)

    reply, source = get_chat_response(user_text, profile, history)
    ai_msg = ChatMessage(
        user_id=current_user.id, role='assistant',
        content=reply, source=source,
    )
    db.session.add(ai_msg)
    db.session.commit()
    log_action('ai_chat', source)

    return jsonify({
        'success': True,
        'data': {
            'user_message': {'id': user_msg.id, 'content': user_text,
                             'created_at': user_msg.created_at.isoformat()},
            'ai_message': {'id': ai_msg.id, 'content': reply, 'source': source,
                           'created_at': ai_msg.created_at.isoformat()},
        }
    })


@app.route('/api/chat/messages')
@login_required
@role_required('user')
def api_chat_messages():
    messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(
        ChatMessage.created_at
    ).limit(50).all()
    return jsonify({
        'success': True,
        'data': [{
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'source': m.source,
            'created_at': m.created_at.isoformat(),
        } for m in messages]
    })


@app.route('/api/chat/clear', methods=['POST'])
@login_required
@role_required('user')
def api_chat_clear():
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    log_action('ai_chat_clear')
    return jsonify({'success': True})


# ─── API ──────────────────────────────────────────────────────────────────────

@app.route('/api/professions')
def api_professions():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    query = Profession.query.filter_by(is_published=True)
    if q:
        query = query.filter(Profession.title.ilike(f'%{q}%'))
    if category:
        query = query.filter_by(category=category)
    items = [{
        'id': p.id,
        'title': p.title,
        'description': p.description,
        'category': p.category,
        'salary_min': p.salary_min,
        'salary_max': p.salary_max,
        'skills_required': p.skills_required,
    } for p in query.all()]
    return jsonify({'success': True, 'data': items, 'count': len(items)})


@app.route('/api/professions/<int:pid>')
def api_profession_detail(pid):
    p = Profession.query.get_or_404(pid)
    return jsonify({
        'success': True,
        'data': {
            'id': p.id,
            'title': p.title,
            'description': p.description,
            'category': p.category,
            'salary_min': p.salary_min,
            'salary_max': p.salary_max,
            'skills_required': p.skills_required,
            'growth_outlook': p.growth_outlook,
        }
    })


@app.route('/api/recommend', methods=['POST'])
@login_required
def api_recommend():
    data = request.get_json(silent=True) or {}
    prof_id = data.get('profession_id') or request.form.get('profession_id')
    if not prof_id:
        return jsonify({'success': False, 'error': 'profession_id қажет'}), 400
    profession = Profession.query.get_or_404(int(prof_id))
    profile = CareerProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        return jsonify({'success': False, 'error': 'Профиль жоқ'}), 400
    score, summary, source = get_career_recommendation(profession, profile)
    rec = CareerRecommendation(
        user_id=current_user.id,
        profession_id=profession.id,
        match_score=score,
        ai_summary=summary,
        status='pending',
    )
    db.session.add(rec)
    db.session.commit()
    return jsonify({
        'success': True,
        'data': {
            'id': rec.id,
            'profession': profession.title,
            'match_score': score,
            'summary': summary,
            'source': source,
            'ai_provider': 'Google Gemini' if source == 'gemini' else 'local',
        }
    })


@app.route('/api/ai/status')
def api_ai_status():
    return jsonify({
        'success': True,
        'data': {
            'gemini_configured': is_gemini_configured(),
            'model': os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash'),
            'provider': 'Google Gemini',
        }
    })


@app.route('/api/stats')
@login_required
@role_required('admin')
def api_stats():
    return jsonify({
        'success': True,
        'data': {
            'users': User.query.count(),
            'professions': Profession.query.count(),
            'requests': ConsultationRequest.query.count(),
            'recommendations': CareerRecommendation.query.count(),
        }
    })


# ─── Errors ───────────────────────────────────────────────────────────────────

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


# ─── Seed ─────────────────────────────────────────────────────────────────────

def seed_database():
    if User.query.first():
        return

    demo_users = [
        ('admin@careerhub.kz', 'admin123', 'Әкімші Айгүл', 'admin'),
        ('manager@careerhub.kz', 'manager123', 'Менеджер Ерлан', 'manager'),
        ('employee@careerhub.kz', 'employee123', 'Қызметкер Дана', 'employee'),
        ('moderator@careerhub.kz', 'moderator123', 'Модератор Асқар', 'moderator'),
        ('user@careerhub.kz', 'user123', 'Клиент Мадина', 'user'),
    ]
    for email, pwd, name, role in demo_users:
        u = User(email=email, password_hash=generate_password_hash(pwd),
                 full_name=name, role=role)
        db.session.add(u)
        db.session.flush()
        db.session.add(CareerProfile(
            user_id=u.id,
            interests='IT, дизайн, білім',
            skills='Python, HTML, CSS',
            education='Бакалавр',
            experience_years=1,
            preferred_field='IT',
        ))

    professions_data = [
        ('Бағдарламашы', 'Web және мобильді қосымшалар әзірлеу', 'IT',
         400000, 1200000, 'Python, JavaScript, SQL', 'Жоғары сұраныс'),
        ('UI/UX Дизайнер', 'Пайдаланушы интерфейстерін жобалау', 'Дизайн',
         350000, 900000, 'Figma, Adobe, UX research', 'Оrta-Joғары'),
        ('Деректер аналитигі', 'Big Data және ML модельдері', 'IT',
         500000, 1500000, 'Python, SQL, статистика', 'Өте жоғары'),
        ('Маркетолог', 'Digital маркетинг стратегиялары', 'Бизнес',
         300000, 800000, 'SMM, SEO, Analytics', 'Оrta'),
        ('Мұғалім', 'Мектепте педагогикалық жұмыс', 'Білім',
         250000, 500000, 'Педагогика, коммуникация', 'Тұрақты'),
        ('Дәрігер', 'Денсаулық сақтау саласында жұмыс', 'Медицина',
         400000, 1000000, 'Медицина, эмпатия', 'Жоғары'),
    ]
    for title, desc, cat, smin, smax, skills, growth in professions_data:
        db.session.add(Profession(
            title=title, description=desc, category=cat,
            salary_min=smin, salary_max=smax,
            skills_required=skills, growth_outlook=growth,
            is_published=True,
        ))

    db.session.commit()

    user = User.query.filter_by(email='user@careerhub.kz').first()
    prof = Profession.query.filter_by(title='Бағдарламашы').first()
    if user and prof:
        db.session.add(CareerRecommendation(
            user_id=user.id, profession_id=prof.id,
            match_score=88,
            ai_summary='Сіздің Python дағдыларыңыз бағдарламашы мамандығына тамаша сәйкес.',
            status='approved',
        ))
        db.session.add(ConsultationRequest(
            client_id=user.id, subject='Мамандық таңдау кеңес',
            message='IT саласына кіргім келеді.', status='new',
        ))
        employee = User.query.filter_by(email='employee@careerhub.kz').first()
        if employee:
            req = ConsultationRequest.query.first()
            db.session.add(WorkTask(
                title='Клиентке кеңес беру',
                description='Мадинаға IT мамандықтарын түсіндіру',
                employee_id=employee.id,
                request_id=req.id if req else None,
                status='assigned',
            ))
    db.session.commit()


def init_database():
    """Production/staging: кестелер + demo деректер."""
    with app.app_context():
        db.create_all()
        seed_database()


if __name__ == '__main__':
    init_database()
    port = int(os.environ.get('PORT', 5005))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
