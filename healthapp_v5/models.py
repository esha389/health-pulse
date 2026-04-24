from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    age        = db.Column(db.Integer)
    gender     = db.Column(db.String(10))
    is_admin   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bp_records       = db.relationship('BloodPressure', backref='user', lazy=True, cascade='all, delete-orphan')
    diabetes_records = db.relationship('Diabetes',      backref='user', lazy=True, cascade='all, delete-orphan')
    thyroid_records  = db.relationship('Thyroid',       backref='user', lazy=True, cascade='all, delete-orphan')
    bmi_records      = db.relationship('BMI',           backref='user', lazy=True, cascade='all, delete-orphan')
    reminders        = db.relationship('Reminder',      backref='user', lazy=True, cascade='all, delete-orphan')
    uploads          = db.relationship('UploadedReport',backref='user', lazy=True, cascade='all, delete-orphan')


class BloodPressure(db.Model):
    __tablename__ = 'blood_pressure'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    systolic    = db.Column(db.Integer, nullable=False)
    diastolic   = db.Column(db.Integer, nullable=False)
    pulse       = db.Column(db.Integer)
    risk_level  = db.Column(db.String(20))
    source      = db.Column(db.String(20), default='manual')
    notes       = db.Column(db.Text)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Diabetes(db.Model):
    __tablename__ = 'diabetes'
    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fasting_glucose      = db.Column(db.Float)
    postprandial_glucose = db.Column(db.Float)
    hba1c                = db.Column(db.Float)
    risk_level           = db.Column(db.String(20))
    source               = db.Column(db.String(20), default='manual')
    notes                = db.Column(db.Text)
    recorded_at          = db.Column(db.DateTime, default=datetime.utcnow)


class Thyroid(db.Model):
    __tablename__ = 'thyroid'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tsh         = db.Column(db.Float)
    t3          = db.Column(db.Float)
    t4          = db.Column(db.Float)
    risk_level  = db.Column(db.String(20))
    source      = db.Column(db.String(20), default='manual')
    notes       = db.Column(db.Text)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class BMI(db.Model):
    __tablename__ = 'bmi'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    height_cm   = db.Column(db.Float, nullable=False)
    weight_kg   = db.Column(db.Float, nullable=False)
    bmi_value   = db.Column(db.Float)
    category    = db.Column(db.String(30))
    risk_level  = db.Column(db.String(20))
    source      = db.Column(db.String(20), default='manual')
    notes       = db.Column(db.Text)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Reminder(db.Model):
    __tablename__ = 'reminders'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title         = db.Column(db.String(200), nullable=False)
    reminder_type = db.Column(db.String(50), default='medication')
    due_date      = db.Column(db.DateTime)
    repeat        = db.Column(db.String(20), default='none')  # none/daily/weekly
    is_done       = db.Column(db.Boolean, default=False)
    notified      = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


class UploadedReport(db.Model):
    __tablename__ = 'uploaded_reports'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    original_filename = db.Column(db.String(300), nullable=False)
    stored_filename   = db.Column(db.String(300), nullable=False)
    file_path         = db.Column(db.String(500), nullable=False)
    file_type         = db.Column(db.String(10))

    test_type         = db.Column(db.String(50))
    test_date         = db.Column(db.DateTime)
    test_year         = db.Column(db.Integer)   # for year-based filtering
    test_month        = db.Column(db.Integer)   # for month-based filtering
    lab_name          = db.Column(db.String(200))
    referring_doctor  = db.Column(db.String(200))
    patient_on_report = db.Column(db.String(200))
    reg_id            = db.Column(db.String(100))

    extracted_json    = db.Column(db.Text)
    ai_summary        = db.Column(db.Text)

    auto_saved        = db.Column(db.Boolean, default=False)
    auto_saved_to     = db.Column(db.String(50))
    uploaded_at       = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def data(self):
        try:
            return json.loads(self.extracted_json) if self.extracted_json else {}
        except Exception:
            return {}

    @property
    def icon(self):
        return {'thyroid':'🔬','blood_pressure':'❤️','diabetes':'🩸','bmi':'⚖️',
                'lipid':'🫀','liver':'🟤','kidney':'💧','cbc':'🔴','other':'📄'
                }.get(self.test_type or 'other', '📄')

    @property
    def label(self):
        return {'thyroid':'Thyroid Profile','blood_pressure':'Blood Pressure',
                'diabetes':'Diabetes / Blood Sugar','bmi':'BMI / Weight',
                'lipid':'Lipid Profile','liver':'Liver Function Test',
                'kidney':'Kidney Function Test','cbc':'Complete Blood Count',
                'other':'Other Report'}.get(self.test_type or 'other', 'Lab Report')

    @property
    def display_date(self):
        return self.test_date or self.uploaded_at


class AppUpdate(db.Model):
    """Admin-managed changelog / announcements."""
    __tablename__ = 'app_updates'
    id         = db.Column(db.Integer, primary_key=True)
    version    = db.Column(db.String(20))
    title      = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text)
    update_type= db.Column(db.String(30), default='feature')  # feature/fix/announcement
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
