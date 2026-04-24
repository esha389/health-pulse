from flask import (Flask, render_template, request, redirect, url_for,
                   flash, send_file, abort, jsonify)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
import os, uuid, json

from models import db, User, BloodPressure, Diabetes, Thyroid, BMI, Reminder, UploadedReport, AppUpdate
from utils.risk_engine import classify_bp, classify_diabetes, classify_thyroid, classify_bmi, overall_risk
from utils.ai_insights import get_insights
from utils.pdf_report import generate
from utils.extractor import extract, parse_date

app = Flask(__name__)
app.config['SECRET_KEY']               = os.environ.get('SECRET_KEY', 'healthtrack-v4-secret-2025')
app.config['SQLALCHEMY_DATABASE_URI']  = 'sqlite:///health.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH']       = 25 * 1024 * 1024

GEMINI_API_KEY     = os.environ.get('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY_HERE')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp'}

db.init_app(app)
lm = LoginManager(app)
lm.login_view = 'login'

@lm.user_loader
def load_user(uid): return User.query.get(int(uid))

def allowed(fn): return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def user_upload_dir(uid):
    d = os.path.join('static', 'uploads', str(uid))
    os.makedirs(d, exist_ok=True)
    return d

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_globals():
    now = datetime.utcnow()
    due_reminders = []
    latest_update = None
    if current_user.is_authenticated:
        due_reminders = Reminder.query.filter(
            Reminder.user_id == current_user.id,
            Reminder.is_done == False,
            Reminder.due_date <= now + timedelta(hours=1),
            Reminder.due_date >= now - timedelta(minutes=5)
        ).all()
        latest_update = AppUpdate.query.order_by(AppUpdate.created_at.desc()).first()
    return {'now': now, 'due_reminders': due_reminders, 'latest_update': latest_update}


# ── API: due reminders for JS polling ─────────────────────────────────────────
@app.route('/api/due-reminders')
@login_required
def api_due_reminders():
    now = datetime.utcnow()
    rems = Reminder.query.filter(
        Reminder.user_id == current_user.id,
        Reminder.is_done == False,
        Reminder.due_date <= now + timedelta(minutes=1),
        Reminder.due_date >= now - timedelta(minutes=10)
    ).all()
    return jsonify([{
        'id': r.id,
        'title': r.title,
        'type': r.reminder_type,
        'due': r.due_date.isoformat() if r.due_date else None
    } for r in rems])


# ══ AUTH ══════════════════════════════════════════════════════════════════════

@app.route('/')
def index(): return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        pw = request.form['password']
        age = request.form.get('age')
        gender = request.form.get('gender')
        if not name or not email or not pw:
            flash('All fields required.', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('register.html')
        # First user is auto-admin
        is_first = User.query.count() == 0
        u = User(name=name, email=email, password=generate_password_hash(pw),
                 age=int(age) if age else None, gender=gender, is_admin=is_first)
        db.session.add(u)
        db.session.commit()
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email'].strip().lower()).first()
        if u and check_password_hash(u.password, request.form['password']):
            login_user(u)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))


# ══ DASHBOARD ════════════════════════════════════════════════════════════════

@app.route('/dashboard')
@login_required
def dashboard():
    uid = current_user.id
    lb   = BloodPressure.query.filter_by(user_id=uid).order_by(BloodPressure.recorded_at.desc()).first()
    ld   = Diabetes.query.filter_by(user_id=uid).order_by(Diabetes.recorded_at.desc()).first()
    lt   = Thyroid.query.filter_by(user_id=uid).order_by(Thyroid.recorded_at.desc()).first()
    lbmi = BMI.query.filter_by(user_id=uid).order_by(BMI.recorded_at.desc()).first()
    risk = overall_risk([x.risk_level if x else None for x in [lb, ld, lt, lbmi]])

    bp_chart = BloodPressure.query.filter_by(user_id=uid).order_by(BloodPressure.recorded_at.asc()).limit(8).all()
    th_chart = Thyroid.query.filter_by(user_id=uid).order_by(Thyroid.recorded_at.asc()).limit(8).all()
    recent_uploads = UploadedReport.query.filter_by(user_id=uid).order_by(UploadedReport.uploaded_at.desc()).limit(5).all()
    pending_reminders = Reminder.query.filter_by(user_id=uid, is_done=False).order_by(Reminder.due_date.asc()).limit(5).all()
    total_reports = UploadedReport.query.filter_by(user_id=uid).count()
    updates = AppUpdate.query.order_by(AppUpdate.created_at.desc()).limit(3).all()

    return render_template('dashboard.html',
        lb=lb, ld=ld, lt=lt, lbmi=lbmi, risk=risk,
        recent_uploads=recent_uploads, pending_reminders=pending_reminders,
        total_reports=total_reports, updates=updates,
        bp_labels=json.dumps([r.recorded_at.strftime('%d %b %Y') for r in bp_chart]),
        bp_sys=json.dumps([r.systolic for r in bp_chart]),
        bp_dia=json.dumps([r.diastolic for r in bp_chart]),
        th_labels=json.dumps([r.recorded_at.strftime('%d %b %Y') for r in th_chart]),
        th_tsh=json.dumps([r.tsh for r in th_chart]),
    )


# ══ HEALTH MODULES ═══════════════════════════════════════════════════════════

@app.route('/blood-pressure', methods=['GET', 'POST'])
@login_required
def blood_pressure():
    if request.method == 'POST':
        sys_ = int(request.form['systolic'])
        dia_ = int(request.form['diastolic'])
        pulse = request.form.get('pulse')
        risk, msg = classify_bp(sys_, dia_)
        db.session.add(BloodPressure(user_id=current_user.id, systolic=sys_, diastolic=dia_,
            pulse=int(pulse) if pulse else None, risk_level=risk, notes=request.form.get('notes', '')))
        db.session.commit()
        flash(msg, 'info')
        return redirect(url_for('blood_pressure'))
    recs = BloodPressure.query.filter_by(user_id=current_user.id).order_by(BloodPressure.recorded_at.desc()).all()
    c = recs[:10][::-1]
    return render_template('blood_pressure.html', records=recs,
        labels=json.dumps([r.recorded_at.strftime('%d %b %Y') for r in c]),
        sys_data=json.dumps([r.systolic for r in c]),
        dia_data=json.dumps([r.diastolic for r in c]))

@app.route('/diabetes', methods=['GET', 'POST'])
@login_required
def diabetes():
    if request.method == 'POST':
        fg = request.form.get('fasting_glucose')
        pp = request.form.get('postprandial_glucose')
        a1c = request.form.get('hba1c')
        fg = float(fg) if fg else None
        pp = float(pp) if pp else None
        a1c = float(a1c) if a1c else None
        risk, msg, _ = classify_diabetes(fg, pp, a1c)
        db.session.add(Diabetes(user_id=current_user.id, fasting_glucose=fg,
            postprandial_glucose=pp, hba1c=a1c, risk_level=risk, notes=request.form.get('notes', '')))
        db.session.commit()
        flash(msg, 'info')
        return redirect(url_for('diabetes'))
    recs = Diabetes.query.filter_by(user_id=current_user.id).order_by(Diabetes.recorded_at.desc()).all()
    c = recs[:10][::-1]
    return render_template('diabetes.html', records=recs,
        labels=json.dumps([r.recorded_at.strftime('%d %b %Y') for r in c]),
        fast_data=json.dumps([r.fasting_glucose for r in c]),
        a1c_data=json.dumps([r.hba1c for r in c]))

@app.route('/thyroid', methods=['GET', 'POST'])
@login_required
def thyroid():
    if request.method == 'POST':
        tsh = request.form.get('tsh')
        t3 = request.form.get('t3')
        t4 = request.form.get('t4')
        tsh = float(tsh) if tsh else None
        t3 = float(t3) if t3 else None
        t4 = float(t4) if t4 else None
        risk, msg, _ = classify_thyroid(tsh, t3, t4)
        db.session.add(Thyroid(user_id=current_user.id, tsh=tsh, t3=t3, t4=t4,
            risk_level=risk, notes=request.form.get('notes', '')))
        db.session.commit()
        flash(msg, 'info')
        return redirect(url_for('thyroid'))
    recs = Thyroid.query.filter_by(user_id=current_user.id).order_by(Thyroid.recorded_at.desc()).all()
    c = recs[:10][::-1]
    return render_template('thyroid.html', records=recs,
        labels=json.dumps([r.recorded_at.strftime('%d %b %Y') for r in c]),
        tsh_data=json.dumps([r.tsh for r in c]),
        t3_data=json.dumps([r.t3 for r in c]),
        t4_data=json.dumps([r.t4 for r in c]))

@app.route('/bmi', methods=['GET', 'POST'])
@login_required
def bmi():
    if request.method == 'POST':
        h = float(request.form['height_cm'])
        w = float(request.form['weight_kg'])
        bmi_v, cat, risk, tip = classify_bmi(h, w)
        db.session.add(BMI(user_id=current_user.id, height_cm=h, weight_kg=w,
            bmi_value=bmi_v, category=cat, risk_level=risk, notes=request.form.get('notes', '')))
        db.session.commit()
        flash(tip, 'info')
        return redirect(url_for('bmi'))
    recs = BMI.query.filter_by(user_id=current_user.id).order_by(BMI.recorded_at.desc()).all()
    c = recs[:10][::-1]
    return render_template('bmi.html', records=recs,
        labels=json.dumps([r.recorded_at.strftime('%d %b %Y') for r in c]),
        bmi_data=json.dumps([r.bmi_value for r in c]),
        wt_data=json.dumps([r.weight_kg for r in c]))


# ══ UPLOAD + AI EXTRACTION ══════════════════════════════════════════════════

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        f = request.files.get('report_file')
        api_key = GEMINI_API_KEY

        if not f or not f.filename:
            flash('Please select a file.', 'error')
            return redirect(url_for('upload'))
        if not allowed(f.filename):
            flash('Only PDF, PNG, JPG, JPEG, WEBP files allowed.', 'error')
            return redirect(url_for('upload'))

        ext = f.filename.rsplit('.', 1)[1].lower()
        sname = f'{uuid.uuid4().hex}.{ext}'
        dir_ = user_upload_dir(current_user.id)
        fpath = os.path.join(dir_, sname)
        f.save(fpath)

        extracted = {}
        err = None
        try:
            extracted = extract(fpath, ext, api_key)
        except Exception as e:
            err = str(e)

        vals = extracted.get('values') or {}
        test_type = extracted.get('test_type', 'other')
        test_dt = parse_date(extracted.get('test_date'))

        rpt = UploadedReport(
            user_id=current_user.id,
            original_filename=secure_filename(f.filename),
            stored_filename=sname, file_path=fpath, file_type=ext,
            test_type=test_type, test_date=test_dt,
            test_year=test_dt.year if test_dt else datetime.utcnow().year,
            test_month=test_dt.month if test_dt else datetime.utcnow().month,
            lab_name=extracted.get('lab_name'),
            referring_doctor=extracted.get('referring_doctor'),
            patient_on_report=extracted.get('patient_name'),
            reg_id=extracted.get('registration_id'),
            extracted_json=json.dumps(extracted),
            ai_summary=extracted.get('summary'),
        )
        db.session.add(rpt)
        db.session.flush()

        saved_to = _auto_save(vals, test_type, test_dt, rpt)
        if saved_to:
            rpt.auto_saved = True
            rpt.auto_saved_to = saved_to
        db.session.commit()

        if err:
            flash(f'⚠️ File saved but AI extraction failed: {err}. Run: pip install pdfplumber Pillow --upgrade', 'error')
        else:
            msg = f'✅ Report uploaded! {len(vals)} value(s) extracted.'
            if saved_to:
                msg += f' Auto-saved to {saved_to.replace("_", " ").title()} tracker.'
            flash(msg, 'success')
        return redirect(url_for('report_detail', rid=rpt.id))

    return render_template('upload.html')


def _auto_save(vals, test_type, test_dt, rpt):
    """Save extracted values to the appropriate health module."""
    ref_dt = test_dt or datetime.utcnow()
    note = f"From {rpt.lab_name or 'lab report'} — {rpt.original_filename}"

    if test_type == 'thyroid' and any(k in vals for k in ('tsh', 't3', 't4')):
        tsh = vals.get('tsh'); t3 = vals.get('t3'); t4 = vals.get('t4')
        risk, _, _ = classify_thyroid(tsh, t3, t4)
        db.session.add(Thyroid(user_id=rpt.user_id, tsh=tsh, t3=t3, t4=t4,
            risk_level=risk, source='report', notes=note, recorded_at=ref_dt))
        return 'thyroid'

    elif test_type == 'blood_pressure' and 'systolic' in vals and 'diastolic' in vals:
        risk, _ = classify_bp(int(vals['systolic']), int(vals['diastolic']))
        db.session.add(BloodPressure(user_id=rpt.user_id,
            systolic=int(vals['systolic']), diastolic=int(vals['diastolic']),
            pulse=int(vals['pulse']) if vals.get('pulse') else None,
            risk_level=risk, source='report', notes=note, recorded_at=ref_dt))
        return 'blood_pressure'

    elif test_type == 'diabetes' and any(k in vals for k in ('fasting_glucose', 'hba1c')):
        fg = vals.get('fasting_glucose'); pp = vals.get('postprandial_glucose'); a1c = vals.get('hba1c')
        risk, _, _ = classify_diabetes(fg, pp, a1c)
        db.session.add(Diabetes(user_id=rpt.user_id, fasting_glucose=fg,
            postprandial_glucose=pp, hba1c=a1c, risk_level=risk,
            source='report', notes=note, recorded_at=ref_dt))
        return 'diabetes'

    return None


# ══ REPORT VAULT ═════════════════════════════════════════════════════════════

@app.route('/vault')
@login_required
def vault():
    ftype = request.args.get('type', 'all')
    fyear = request.args.get('year', 'all')
    q = UploadedReport.query.filter_by(user_id=current_user.id)
    if ftype != 'all':
        q = q.filter_by(test_type=ftype)
    if fyear != 'all':
        q = q.filter_by(test_year=int(fyear))

    rpts = q.order_by(UploadedReport.test_date.desc().nullslast(),
                      UploadedReport.uploaded_at.desc()).all()

    # Group by Year → Month
    grouped = {}
    for r in rpts:
        yr = r.display_date.year
        mo = r.display_date.strftime('%B %Y')
        grouped.setdefault(yr, {}).setdefault(mo, []).append(r)

    all_rpts = UploadedReport.query.filter_by(user_id=current_user.id).all()
    counts = {}
    years = set()
    for r in all_rpts:
        counts[r.test_type] = counts.get(r.test_type, 0) + 1
        if r.test_year:
            years.add(r.test_year)

    return render_template('vault.html', grouped=grouped, ftype=ftype, fyear=fyear,
                           counts=counts, total=len(all_rpts), years=sorted(years, reverse=True))


@app.route('/vault/<int:rid>')
@login_required
def report_detail(rid):
    r = UploadedReport.query.get_or_404(rid)
    if r.user_id != current_user.id:
        abort(403)
    return render_template('report_detail.html', r=r)


@app.route('/vault/<int:rid>/file')
@login_required
def serve_file(rid):
    r = UploadedReport.query.get_or_404(rid)
    if r.user_id != current_user.id:
        abort(403)
    mimes = {'pdf': 'application/pdf', 'png': 'image/png',
             'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}
    return send_file(r.file_path, mimetype=mimes.get(r.file_type, 'application/octet-stream'))


@app.route('/vault/<int:rid>/delete', methods=['POST'])
@login_required
def delete_report(rid):
    r = UploadedReport.query.get_or_404(rid)
    if r.user_id != current_user.id:
        abort(403)
    try:
        os.remove(r.file_path)
    except Exception:
        pass
    db.session.delete(r)
    db.session.commit()
    flash('Report deleted.', 'success')
    return redirect(url_for('vault'))


# ── Re-extract route (MUST be before if __name__) ────────────────────────────
@app.route('/vault/<int:rid>/reextract', methods=['POST'])
@login_required
def reextract(rid):
    r = UploadedReport.query.get_or_404(rid)
    if r.user_id != current_user.id:
        abort(403)
    api_key = GEMINI_API_KEY
    try:
        extracted = extract(r.file_path, r.file_type, api_key)
    except Exception as e:
        flash(f'❌ Extraction failed: {e}. Run: pip install pdfplumber Pillow --upgrade', 'error')
        return redirect(url_for('report_detail', rid=rid))

    vals = extracted.get('values') or {}
    test_dt = parse_date(extracted.get('test_date'))
    test_type = extracted.get('test_type', 'other')

    r.test_type         = test_type
    r.test_date         = test_dt or r.test_date
    r.test_year         = (test_dt or r.uploaded_at).year
    r.test_month        = (test_dt or r.uploaded_at).month
    r.lab_name          = extracted.get('lab_name') or r.lab_name
    r.referring_doctor  = extracted.get('referring_doctor') or r.referring_doctor
    r.patient_on_report = extracted.get('patient_name') or r.patient_on_report
    r.reg_id            = extracted.get('registration_id') or r.reg_id
    r.extracted_json    = json.dumps(extracted)
    r.ai_summary        = extracted.get('summary')

    if not r.auto_saved:
        saved_to = _auto_save(vals, test_type, test_dt, r)
        if saved_to:
            r.auto_saved = True
            r.auto_saved_to = saved_to

    db.session.commit()

    flags = extracted.get('abnormal_flags', [])
    msg = f'✅ Re-extraction successful! {len(vals)} value(s) found.'
    if flags:
        msg += f' {len(flags)} abnormal flag(s).'
    if r.auto_saved:
        msg += f' Saved to {r.auto_saved_to.replace("_"," ").title()} module.'
    flash(msg, 'success')
    return redirect(url_for('report_detail', rid=rid))


@app.route('/doctor-view')
@login_required
def doctor_view():
    rpts = UploadedReport.query.filter_by(user_id=current_user.id)\
        .order_by(UploadedReport.test_date.desc().nullslast(),
                  UploadedReport.uploaded_at.desc()).all()
    return render_template('doctor_view.html', reports=rpts)


# ══ ALL REPORTS ═══════════════════════════════════════════════════════════════

@app.route('/reports')
@login_required
def reports():
    uid = current_user.id
    return render_template('reports.html',
        bp_recs  = BloodPressure.query.filter_by(user_id=uid).order_by(BloodPressure.recorded_at.desc()).all(),
        dm_recs  = Diabetes.query.filter_by(user_id=uid).order_by(Diabetes.recorded_at.desc()).all(),
        th_recs  = Thyroid.query.filter_by(user_id=uid).order_by(Thyroid.recorded_at.desc()).all(),
        bmi_recs = BMI.query.filter_by(user_id=uid).order_by(BMI.recorded_at.desc()).all())


# ══ AI INSIGHTS ═══════════════════════════════════════════════════════════════

@app.route('/insights', methods=['GET', 'POST'])
@login_required
def insights():
    ai_resp = None; err = None
    if request.method == 'POST':
        uid = current_user.id
        def lat(M): return M.query.filter_by(user_id=uid).order_by(M.recorded_at.desc()).first()
        lb = lat(BloodPressure); ld = lat(Diabetes); lt = lat(Thyroid); lbmi = lat(BMI)
        data = {
            'name': current_user.name, 'age': current_user.age, 'gender': current_user.gender,
            'blood_pressure': {'systolic': lb.systolic if lb else None, 'diastolic': lb.diastolic if lb else None, 'risk': lb.risk_level if lb else None},
            'diabetes': {'fasting': ld.fasting_glucose if ld else None, 'hba1c': ld.hba1c if ld else None, 'risk': ld.risk_level if ld else None},
            'thyroid': {'tsh': lt.tsh if lt else None, 't3': lt.t3 if lt else None, 't4': lt.t4 if lt else None, 'risk': lt.risk_level if lt else None},
            'bmi': {'value': lbmi.bmi_value if lbmi else None, 'category': lbmi.category if lbmi else None, 'risk': lbmi.risk_level if lbmi else None},
        }
        api_key = GEMINI_API_KEY
        try:
            ai_resp = get_insights(data, api_key)
        except Exception as e:
            err = f'AI Error: {e}'
    return render_template('insights.html', ai_resp=ai_resp, err=err)


# ══ PDF EXPORT ════════════════════════════════════════════════════════════════

@app.route('/export-pdf', methods=['POST'])
@login_required
def export_pdf():
    uid = current_user.id
    api_key = GEMINI_API_KEY
    bp  = BloodPressure.query.filter_by(user_id=uid).order_by(BloodPressure.recorded_at.desc()).limit(10).all()
    dm  = Diabetes.query.filter_by(user_id=uid).order_by(Diabetes.recorded_at.desc()).limit(10).all()
    th  = Thyroid.query.filter_by(user_id=uid).order_by(Thyroid.recorded_at.desc()).limit(10).all()
    bmi_ = BMI.query.filter_by(user_id=uid).order_by(BMI.recorded_at.desc()).limit(10).all()
    ai_text = None
    if request.form.get('include_ai') == 'yes':
        try:
            data = {'name': current_user.name, 'age': current_user.age,
                    'thyroid': {'tsh': th[0].tsh if th else None, 'risk': th[0].risk_level if th else None},
                    'blood_pressure': {'systolic': bp[0].systolic if bp else None, 'risk': bp[0].risk_level if bp else None},
                    'diabetes': {'fasting': dm[0].fasting_glucose if dm else None, 'risk': dm[0].risk_level if dm else None},
                    'bmi': {'value': bmi_[0].bmi_value if bmi_ else None}}
            ai_text = get_insights(data, api_key)
        except Exception:
            pass
    path = generate(current_user, bp, dm, th, bmi_, ai_text)
    return send_file(path, as_attachment=True,
                     download_name=f'HealthReport_{current_user.name.replace(" ","_")}.pdf',
                     mimetype='application/pdf')


# ══ REMINDERS ════════════════════════════════════════════════════════════════

@app.route('/reminders', methods=['GET', 'POST'])
@login_required
def reminders():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        due   = request.form.get('due_date')
        if title and due:
            db.session.add(Reminder(
                user_id=current_user.id, title=title,
                reminder_type=request.form.get('reminder_type', 'medication'),
                repeat=request.form.get('repeat', 'none'),
                due_date=datetime.strptime(due, '%Y-%m-%dT%H:%M')
            ))
            db.session.commit()
            flash('Reminder set! You\'ll get a browser notification when it\'s due. ✅', 'success')
        return redirect(url_for('reminders'))
    rems = Reminder.query.filter_by(user_id=current_user.id).order_by(Reminder.due_date.asc()).all()
    return render_template('reminders.html', reminders=rems)

@app.route('/reminders/<int:rid>/done', methods=['POST'])
@login_required
def reminder_done(rid):
    r = Reminder.query.get_or_404(rid)
    if r.user_id == current_user.id:
        r.is_done = True
        db.session.commit()
    return redirect(url_for('reminders'))

@app.route('/reminders/<int:rid>/delete', methods=['POST'])
@login_required
def reminder_delete(rid):
    r = Reminder.query.get_or_404(rid)
    if r.user_id == current_user.id:
        db.session.delete(r)
        db.session.commit()
    return redirect(url_for('reminders'))


# ══ DELETE HEALTH RECORDS ════════════════════════════════════════════════════

@app.route('/delete/bp/<int:id>', methods=['POST'])
@login_required
def del_bp(id):
    r = BloodPressure.query.get_or_404(id)
    if r.user_id == current_user.id: db.session.delete(r); db.session.commit()
    return redirect(url_for('blood_pressure'))

@app.route('/delete/diabetes/<int:id>', methods=['POST'])
@login_required
def del_dm(id):
    r = Diabetes.query.get_or_404(id)
    if r.user_id == current_user.id: db.session.delete(r); db.session.commit()
    return redirect(url_for('diabetes'))

@app.route('/delete/thyroid/<int:id>', methods=['POST'])
@login_required
def del_th(id):
    r = Thyroid.query.get_or_404(id)
    if r.user_id == current_user.id: db.session.delete(r); db.session.commit()
    return redirect(url_for('thyroid'))

@app.route('/delete/bmi/<int:id>', methods=['POST'])
@login_required
def del_bmi(id):
    r = BMI.query.get_or_404(id)
    if r.user_id == current_user.id: db.session.delete(r); db.session.commit()
    return redirect(url_for('bmi'))


# ══ ADMIN ════════════════════════════════════════════════════════════════════

@app.route('/admin')
@login_required
@admin_required
def admin():
    users   = User.query.order_by(User.created_at.desc()).all()
    updates = AppUpdate.query.order_by(AppUpdate.created_at.desc()).all()
    total_uploads = UploadedReport.query.count()
    total_records = (BloodPressure.query.count() + Diabetes.query.count() +
                     Thyroid.query.count() + BMI.query.count())
    return render_template('admin.html', users=users, updates=updates,
                           total_uploads=total_uploads, total_records=total_records)

@app.route('/admin/update', methods=['POST'])
@login_required
@admin_required
def admin_post_update():
    db.session.add(AppUpdate(
        version=request.form.get('version', ''),
        title=request.form['title'],
        body=request.form.get('body', ''),
        update_type=request.form.get('update_type', 'feature')
    ))
    db.session.commit()
    flash('Update posted!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/update/<int:uid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_update(uid):
    u = AppUpdate.query.get_or_404(uid)
    db.session.delete(u)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:uid>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(uid):
    u = User.query.get_or_404(uid)
    if u.id != current_user.id:
        u.is_admin = not u.is_admin
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:uid>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(uid):
    u = User.query.get_or_404(uid)
    if u.id != current_user.id:
        db.session.delete(u)
        db.session.commit()
        flash(f'User {u.name} deleted.', 'success')
    return redirect(url_for('admin'))


# ══ MAIN ══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('✅ HealthTrack Pro v4 — Database ready.')
        print('🔑 First user to register becomes admin automatically.')
    app.run(debug=True)