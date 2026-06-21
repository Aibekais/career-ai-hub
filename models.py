from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    # admin | manager | employee | moderator | user
    is_active = db.Column(db.Boolean, default=True)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profile = db.relationship('CareerProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    requests = db.relationship('ConsultationRequest', backref='client', lazy=True, foreign_keys='ConsultationRequest.client_id')
    tasks = db.relationship('WorkTask', backref='assignee', lazy=True, foreign_keys='WorkTask.employee_id')
    recommendations = db.relationship(
        'CareerRecommendation',
        backref='user',
        lazy=True,
        foreign_keys='CareerRecommendation.user_id',
    )

    def has_role(self, *roles):
        return self.role in roles


class CareerProfile(db.Model):
    __tablename__ = 'career_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    interests = db.Column(db.Text)
    skills = db.Column(db.Text)
    education = db.Column(db.String(200))
    experience_years = db.Column(db.Integer, default=0)
    preferred_field = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Profession(db.Model):
    __tablename__ = 'professions'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(80))
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    skills_required = db.Column(db.Text)
    growth_outlook = db.Column(db.String(200))
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recommendations = db.relationship('CareerRecommendation', backref='profession', lazy=True)


class CareerRecommendation(db.Model):
    __tablename__ = 'career_recommendations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profession_id = db.Column(db.Integer, db.ForeignKey('professions.id'), nullable=False)
    match_score = db.Column(db.Integer, default=0)
    ai_summary = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending | approved | rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ConsultationRequest(db.Model):
    __tablename__ = 'consultation_requests'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='new')  # new | in_progress | done | cancelled
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = db.relationship('User', foreign_keys=[manager_id])


class WorkTask(db.Model):
    __tablename__ = 'work_tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('consultation_requests.id'))
    status = db.Column(db.String(20), default='assigned')  # assigned | in_progress | completed
    due_date = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PublishedMaterial(db.Model):
    __tablename__ = 'published_materials'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending | approved | rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', foreign_keys=[author_id])


class SystemLog(db.Model):
    __tablename__ = 'system_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(20), default='gemini')  # gemini | local
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('chat_messages', lazy=True, order_by='ChatMessage.created_at'))
