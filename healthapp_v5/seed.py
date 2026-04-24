"""
HealthPulse — 3-Year Dense Test Data Seeder
============================================
Dense monthly+ readings for all modules.
Thyroid: 60 entries | BP: 80 entries | Sugar: 55 entries | BMI: 18 entries

Run from your project folder:
    python seed_data.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, User, Thyroid, BloodPressure, Diabetes, BMI
from werkzeug.security import generate_password_hash
from datetime import datetime
import random

random.seed(99)

def dt(year, month, day, hour=8):
    return datetime(year, month, day, hour, random.randint(0, 59))

def jitter(val, pct=0.04):
    return round(val * (1 + random.uniform(-pct, pct)), 3)

def ji(val, delta=2):
    return val + random.randint(-delta, delta)

# ── Risk classifiers ─────────────────────────────────────────────────────────

def risk_tsh(tsh):
    if tsh is None: return 'Normal'
    if tsh > 10:    return 'Critical'
    if tsh > 4.78:  return 'High'
    if tsh < 0.55:  return 'Low'
    return 'Normal'

def risk_bp(s, d):
    if s >= 140 or d >= 90: return 'High'
    if s >= 130 or d >= 80: return 'Medium'
    return 'Normal'

def risk_dm(fg, a1c):
    if (fg and fg >= 126) or (a1c and a1c >= 6.5): return 'High'
    if (fg and fg >= 100) or (a1c and a1c >= 5.7): return 'Medium'
    return 'Normal'

def calc_bmi(h, w):
    v = round(w / (h/100)**2, 1)
    cat = 'Obese' if v>=30 else 'Overweight' if v>=25 else 'Underweight' if v<18.5 else 'Normal Weight'
    risk = 'High' if v>=30 else 'Medium' if v>=25 else 'Normal'
    return v, cat, risk

# ════════════════════════════════════════════════════════════════════════════
# THYROID — 60 entries  (Jan 2022 → Apr 2026)
# Story: Undiagnosed hypothyroidism → diagnosis → Levothyroxine → slow normalisation
# ════════════════════════════════════════════════════════════════════════════
thyroid_data = [
    # 2022 — Undiagnosed, progressively worsening, multiple checks
    (2022,  1,  5, 16.80, 1.00, 6.30, 'manual', 'Fatigue, weight gain — first check'),
    (2022,  1, 28, 18.52, 0.98, 6.10, 'manual', 'Repeat — confirming elevation'),
    (2022,  2, 14, 19.10, 0.96, 6.00, 'report', 'Vijaya Diagnostic — Feb 2022'),
    (2022,  3,  3, 20.35, 0.95, 5.95, 'manual', 'Monthly monitoring'),
    (2022,  3, 25, 21.50, 0.93, 5.90, 'report', 'Vijaya Diagnostic — Mar 2022'),
    (2022,  4, 10, 22.10, 0.92, 5.85, 'manual', 'Follow-up — still symptomatic'),
    (2022,  4, 28, 23.40, 0.91, 5.80, 'report', 'Apollo Hyderabad — Apr 2022'),
    (2022,  5, 15, 24.80, 0.90, 5.75, 'manual', 'Worsening fatigue, hair loss noted'),
    (2022,  6,  6, 25.60, 0.89, 5.70, 'report', 'Vijaya Diagnostic — Jun 2022'),
    (2022,  6, 25, 26.20, 0.89, 5.65, 'manual', 'Monthly check'),
    (2022,  7, 14, 27.10, 0.88, 5.60, 'manual', 'Ongoing monitoring'),
    (2022,  8,  2, 28.45, 0.88, 5.50, 'report', 'Vijaya Diagnostic — Aug 2022'),
    (2022,  8, 22, 29.30, 0.87, 5.45, 'manual', 'Follow-up post-Vijaya report'),
    (2022,  9, 12, 30.10, 0.86, 5.38, 'report', 'Thyrocare — Sep 2022'),
    (2022,  9, 30, 30.80, 0.86, 5.30, 'manual', 'Monthly check'),
    (2022, 10, 18, 31.50, 0.85, 5.25, 'manual', 'Referred to endocrinologist'),
    (2022, 11,  5, 31.80, 0.85, 5.20, 'report', 'Vijaya Diagnostic — Nov 2022'),
    (2022, 11, 25, 32.40, 0.84, 5.15, 'manual', 'Pre-consultation baseline'),
    (2022, 12, 10, 38.90, 0.83, 5.10, 'report', 'Metropolis — Dec 2022 comprehensive'),
    (2022, 12, 28, 40.20, 0.82, 5.05, 'manual', 'Year-end — awaiting specialist'),

    # 2023 — Diagnosis + Treatment starts
    (2023,  1, 10, 45.33, 0.80, 4.90, 'report', 'Vijaya — peak TSH, diagnosis confirmed'),
    (2023,  1, 28, 43.80, 0.80, 4.92, 'manual', 'Pre-medication baseline repeat'),
    (2023,  2, 14, 42.10, 0.82, 5.00, 'report', 'Thyrocare — Feb 2023 pre-treatment'),
    (2023,  2, 28, 41.50, 0.82, 5.05, 'manual', 'Last reading before medication'),
    (2023,  3, 15, 39.20, 0.83, 5.10, 'report', 'Vijaya — 2 wks after Levothyroxine 25mcg'),
    (2023,  4,  3, 35.20, 0.88, 5.40, 'report', 'Vijaya — dose adjusted to 50mcg'),
    (2023,  4, 22, 32.60, 0.90, 5.60, 'manual', 'Monthly follow-up'),
    (2023,  5, 10, 28.80, 0.93, 5.85, 'report', 'Apollo — May 2023 follow-up'),
    (2023,  5, 28, 26.10, 0.95, 6.00, 'manual', 'Symptoms improving'),
    (2023,  6, 15, 22.80, 0.97, 6.20, 'report', 'Vijaya Diagnostic — Jun 2023'),
    (2023,  7,  2, 19.50, 1.00, 6.50, 'manual', 'Good response to medication'),
    (2023,  7, 20, 17.80, 1.03, 6.80, 'report', 'Vijaya — July 2023'),
    (2023,  8, 10, 15.33, 1.05, 7.00, 'report', 'Vijaya Diagnostic — Aug 2023'),
    (2023,  8, 28, 13.20, 1.08, 7.20, 'manual', 'Monthly check — energy returning'),
    (2023,  9, 15, 11.40, 1.10, 7.50, 'report', 'Thyrocare — Sep 2023'),
    (2023, 10,  5,  9.10, 1.15, 7.80, 'report', 'Vijaya — dose raised to 75mcg'),
    (2023, 10, 24,  7.85, 1.18, 8.00, 'manual', 'Post dose-increase check'),
    (2023, 11, 12,  7.10, 1.20, 8.20, 'report', 'Apollo — Nov 2023'),
    (2023, 11, 30,  6.65, 1.21, 8.35, 'manual', 'Monthly monitoring'),
    (2023, 12, 12,  6.31, 1.22, 8.40, 'report', 'Vijaya Diagnostic — Dec 2023'),

    # 2024 — Normalising
    (2024,  1, 10,  5.80, 1.26, 8.70, 'manual', 'New year check — approaching normal'),
    (2024,  2,  5,  5.20, 1.30, 9.00, 'report', 'Vijaya — Feb 2024'),
    (2024,  2, 20,  4.65, 1.35, 9.20, 'manual', 'First reading within normal range!'),
    (2024,  3, 15,  4.10, 1.38, 9.40, 'report', 'Apollo Hyderabad — Mar 2024'),
    (2024,  4,  8,  3.80, 1.40, 9.60, 'manual', 'Stable normal range'),
    (2024,  5,  8,  3.20, 1.42, 9.80, 'report', 'Apollo — 6-month milestone check'),
    (2024,  6, 12,  2.95, 1.45, 10.0, 'manual', 'Excellent control'),
    (2024,  7, 10,  2.70, 1.48, 10.2, 'report', 'Vijaya — Jul 2024'),
    (2024,  8, 14,  2.45, 1.52, 10.5, 'report', 'Vijaya Diagnostic — Aug 2024'),
    (2024,  9, 18,  2.30, 1.53, 10.6, 'manual', 'Quarterly check'),
    (2024, 10, 20,  2.20, 1.54, 10.7, 'report', 'Thyrocare — Oct 2024'),
    (2024, 11, 19,  1.98, 1.55, 10.8, 'report', 'Vijaya Diagnostic — Nov 2024'),
    (2024, 12, 28,  2.05, 1.56, 10.9, 'manual', 'Year-end check — stable'),

    # 2025 — Stable normal
    (2025,  2,  6,  2.18, 1.60, 11.1, 'report', 'Vijaya Diagnostic — Feb 2025'),
    (2025,  5, 22,  1.85, 1.62, 11.2, 'report', 'Vijaya Diagnostic — May 2025'),
    (2025,  9, 24,  2.34, 1.58, 10.9, 'report', 'Vijaya Diagnostic — Sep 2025'),
    (2025, 11,  5, 19.07, 1.04, 11.4, 'report', 'Vijaya Diagnostic — Nov 2025 (spike)'),
    (2025, 12,  2, 15.33, 1.35,  7.5, 'report', 'Vijaya Diagnostic — Dec 2025'),

    # 2026
    (2026,  1, 15,  9.80, 1.20,  8.8, 'report', 'Vijaya — Jan 2026 re-check'),
    (2026,  2, 28,  6.31, 1.04,  7.7, 'report', 'Vijaya Diagnostic — Feb 2026'),
    (2026,  4,  5,  4.10, 1.38,  9.4, 'report', 'Vijaya — Apr 2026 latest'),
]

# ════════════════════════════════════════════════════════════════════════════
# BLOOD PRESSURE — 80 entries  (Jan 2022 → Apr 2026)
# Story: Stage 1 HTN → lifestyle improvement → sustained normal
# ════════════════════════════════════════════════════════════════════════════
bp_data = [
    # 2022 — Elevated, multiple readings
    (2022,  1,  3, 138, 88, 82, 'manual', 'Morning reading — high stress'),
    (2022,  1, 12, 140, 89, 84, 'manual', 'Afternoon reading'),
    (2022,  1, 25, 142, 90, 85, 'manual', 'Evening — after coffee'),
    (2022,  2,  5, 139, 88, 83, 'manual', 'Morning check'),
    (2022,  2, 18, 141, 89, 85, 'report', 'Clinic visit — Stage 1 hypertension noted'),
    (2022,  3,  2, 143, 91, 86, 'manual', 'Elevated — work stress'),
    (2022,  3, 15, 140, 89, 84, 'manual', 'Morning reading'),
    (2022,  3, 28, 138, 88, 82, 'manual', 'Routine check'),
    (2022,  4,  8, 136, 87, 81, 'manual', 'Slightly better'),
    (2022,  4, 20, 142, 91, 86, 'report', 'Clinic — BP monitoring'),
    (2022,  5,  3, 139, 88, 83, 'manual', 'Home reading'),
    (2022,  5, 18, 135, 86, 80, 'manual', 'After morning walk'),
    (2022,  6,  2, 138, 88, 82, 'manual', 'Pre-breakfast'),
    (2022,  6, 16, 140, 89, 84, 'manual', 'Midday reading'),
    (2022,  7,  1, 141, 90, 85, 'report', 'Clinic — BP check'),
    (2022,  7, 18, 137, 87, 81, 'manual', 'Post-yoga reading'),
    (2022,  8,  2, 136, 86, 80, 'manual', 'Morning — started yoga'),
    (2022,  8, 15, 138, 87, 82, 'manual', 'Evening reading'),
    (2022,  9,  5, 134, 85, 79, 'manual', 'Diet modification started'),
    (2022,  9, 20, 132, 85, 78, 'manual', 'Good response to diet'),
    (2022, 10,  4, 135, 86, 80, 'report', 'Clinic follow-up'),
    (2022, 10, 18, 133, 85, 79, 'manual', 'Consistent improvement'),
    (2022, 11,  2, 131, 84, 78, 'manual', 'Walking 30 min daily'),
    (2022, 11, 16, 130, 84, 77, 'manual', 'Weekly check'),
    (2022, 12,  1, 132, 85, 79, 'manual', 'Monthly average check'),
    (2022, 12, 20, 129, 83, 77, 'manual', 'Year-end — improving'),

    # 2023 — Continued improvement
    (2023,  1,  5, 128, 82, 76, 'manual', 'New year — committed to exercise'),
    (2023,  1, 20, 126, 81, 75, 'manual', 'Good reading'),
    (2023,  2,  3, 127, 82, 76, 'manual', 'Morning check'),
    (2023,  2, 17, 125, 80, 74, 'report', 'Clinic — progress noted'),
    (2023,  3,  4, 128, 82, 76, 'manual', 'Routine morning'),
    (2023,  3, 19, 124, 80, 74, 'manual', 'Good control'),
    (2023,  4,  3, 126, 81, 75, 'manual', 'Monthly check'),
    (2023,  4, 20, 130, 84, 79, 'manual', 'Exam stress spike'),
    (2023,  5,  5, 125, 80, 74, 'manual', 'Back to normal'),
    (2023,  5, 22, 123, 79, 73, 'manual', 'Good control'),
    (2023,  6,  7, 122, 79, 73, 'report', 'Clinic — BP check'),
    (2023,  6, 22, 120, 78, 72, 'manual', 'Milestone — below 120/80'),
    (2023,  7,  8, 118, 77, 71, 'manual', 'Post-morning walk'),
    (2023,  7, 24, 120, 78, 72, 'manual', 'Afternoon reading'),
    (2023,  8,  9, 119, 77, 71, 'manual', 'Consistent'),
    (2023,  8, 25, 117, 76, 70, 'manual', 'Great reading'),
    (2023,  9,  5, 118, 77, 71, 'manual', 'Yoga + diet change'),
    (2023,  9, 20, 116, 75, 70, 'report', 'Clinic — target BP achieved'),
    (2023, 10,  6, 119, 77, 72, 'manual', 'Routine check'),
    (2023, 10, 22, 120, 78, 73, 'manual', 'Evening reading'),
    (2023, 11,  5, 118, 76, 71, 'manual', 'Consistent control'),
    (2023, 11, 22, 124, 80, 74, 'manual', 'Post-Diwali — slight rise'),
    (2023, 12,  6, 121, 78, 72, 'manual', 'Back to normal'),
    (2023, 12, 28, 119, 77, 71, 'manual', 'Year-end — stable'),

    # 2024 — Normal range maintained
    (2024,  1, 10, 120, 78, 73, 'manual', 'New year — target maintained'),
    (2024,  1, 25, 118, 76, 71, 'manual', 'Morning reading'),
    (2024,  2,  8, 117, 76, 70, 'report', 'Clinic check — excellent'),
    (2024,  2, 22, 116, 75, 70, 'manual', 'Consistent'),
    (2024,  3,  7, 118, 76, 71, 'manual', 'Monthly check'),
    (2024,  3, 22, 115, 74, 69, 'manual', 'Best reading yet'),
    (2024,  4,  5, 117, 75, 70, 'manual', 'Stable'),
    (2024,  4, 20, 119, 77, 72, 'report', 'Clinic — annual review'),
    (2024,  5,  8, 116, 75, 70, 'manual', 'Maintaining well'),
    (2024,  5, 24, 118, 76, 71, 'manual', 'Morning reading'),
    (2024,  6,  9, 120, 78, 73, 'manual', 'Post-exercise check'),
    (2024,  6, 25, 117, 76, 70, 'manual', 'Weekly reading'),
    (2024,  7, 10, 122, 79, 74, 'manual', 'Summer heat — slight rise'),
    (2024,  7, 28, 120, 78, 72, 'manual', 'Back to normal'),
    (2024,  8, 14, 118, 76, 71, 'manual', 'Consistent'),
    (2024,  8, 30, 119, 77, 72, 'manual', 'Stable'),
    (2024,  9, 14, 117, 75, 70, 'report', 'Clinic — quarterly check'),
    (2024, 10,  5, 120, 78, 73, 'manual', 'Routine check'),
    (2024, 10, 22, 118, 76, 71, 'manual', 'Evening reading'),
    (2024, 11,  8, 119, 77, 72, 'manual', 'Stable'),
    (2024, 11, 25, 121, 78, 73, 'manual', 'Post-lunch reading'),
    (2024, 12, 10, 118, 76, 71, 'manual', 'Morning check'),
    (2024, 12, 28, 120, 78, 73, 'manual', 'Year-end — excellent control'),

    # 2025-2026 — Sustained normal
    (2025,  1, 12, 117, 75, 70, 'manual', 'New year — consistent'),
    (2025,  2, 18, 119, 77, 72, 'report', 'Clinic — annual check'),
    (2025,  3, 10, 118, 76, 71, 'manual', 'Morning reading'),
    (2025,  4, 22, 116, 75, 70, 'manual', 'Good control'),
    (2025,  6,  5, 120, 78, 73, 'manual', 'Summer check'),
    (2025,  8, 14, 118, 76, 71, 'report', 'Clinic — BP stable'),
    (2025, 10, 20, 121, 79, 74, 'manual', 'Routine'),
    (2025, 12, 15, 119, 77, 72, 'manual', 'Year-end'),
    (2026,  2, 10, 118, 76, 71, 'report', 'Clinic — latest check'),
    (2026,  4,  5, 120, 78, 73, 'manual', 'April reading'),
]

# ════════════════════════════════════════════════════════════════════════════
# BLOOD SUGAR — 55 entries  (Jan 2022 → Apr 2026)
# Story: Pre-diabetic → diet control → normal sustained
# ════════════════════════════════════════════════════════════════════════════
diabetes_data = [
    # 2022 — Pre-diabetic, close monitoring
    (2022,  1,  8, 108,  162,  6.1, 'manual', 'Annual check — pre-diabetic range detected'),
    (2022,  1, 22, 110,  165,  6.1, 'report', 'Vijaya Diagnostic — fasting glucose'),
    (2022,  2,  5, 109,  164,  6.1, 'manual', 'Repeat check — confirming'),
    (2022,  2, 20, 111,  167,  6.2, 'report', 'Apollo — diabetes screening panel'),
    (2022,  3,  8, 112,  168,  6.2, 'manual', 'Monthly monitoring'),
    (2022,  3, 25, 113,  170,  6.2, 'report', 'Thyrocare — Mar 2022'),
    (2022,  4, 10, 114,  172,  6.3, 'manual', 'Dietician consultation done'),
    (2022,  4, 28, 115,  173,  6.3, 'report', 'Vijaya — pre-diet baseline'),
    (2022,  5, 12, 114,  171,  6.3, 'manual', 'Low GI diet started'),
    (2022,  5, 28, 112,  168,  6.2, 'manual', 'Early response to diet'),
    (2022,  6, 10, 113,  170,  6.2, 'report', 'Vijaya Diagnostic — Jun 2022'),
    (2022,  6, 25, 111,  167,  6.2, 'manual', 'Monthly check'),
    (2022,  7,  8, 112,  168,  6.3, 'manual', 'Summer high-carb eating'),
    (2022,  7, 22, 110,  165,  6.2, 'report', 'Metropolis — Jul 2022'),
    (2022,  8,  5, 111,  166,  6.2, 'manual', 'Back on track with diet'),
    (2022,  8, 20, 109,  164,  6.1, 'report', 'Vijaya — Aug 2022'),
    (2022,  9,  8, 110,  165,  6.1, 'manual', 'Monthly check'),
    (2022,  9, 25, 108,  163,  6.1, 'manual', 'Improving'),
    (2022, 10, 10, 109,  164,  6.1, 'report', 'Vijaya Diagnostic — Oct 2022'),
    (2022, 10, 28, 108,  162,  6.1, 'manual', 'Consistent'),
    (2022, 11, 12, 110,  166,  6.1, 'manual', 'Festival season — slight rise'),
    (2022, 12,  5, 107,  161,  6.0, 'report', 'Vijaya — quarterly check'),
    (2022, 12, 28, 106,  160,  6.0, 'manual', 'Year-end — improving trend'),

    # 2023 — Active improvement
    (2023,  1, 10, 106,  158,  6.0, 'report', 'Vijaya — quarterly check Jan 2023'),
    (2023,  2,  5, 104,  155,  5.9, 'manual', 'Low GI diet showing results'),
    (2023,  2, 22, 103,  152,  5.9, 'report', 'Apollo — Feb 2023'),
    (2023,  3, 10, 102,  150,  5.9, 'manual', 'Good progress'),
    (2023,  4,  5, 101,  148,  5.8, 'report', 'Vijaya — Apr 2023'),
    (2023,  4, 22, 100,  146,  5.8, 'manual', 'Approaching normal'),
    (2023,  5,  8,  99,  144,  5.8, 'report', 'Thyrocare — May 2023'),
    (2023,  5, 25,  98,  142,  5.7, 'manual', 'Normal fasting range achieved'),
    (2023,  6, 10,  97,  141,  5.7, 'report', 'Vijaya Diagnostic — Jun 2023'),
    (2023,  7, 14,  96,  140,  5.6, 'report', 'Vijaya — Jul 2023 quarterly'),
    (2023,  7, 30,  95,  138,  5.6, 'manual', 'Consistent normal range'),
    (2023,  8, 15,  96,  139,  5.6, 'report', 'Apollo — Aug 2023'),
    (2023,  9,  5,  94,  136,  5.6, 'manual', 'Good control'),
    (2023, 10, 10,  95,  138,  5.5, 'report', 'Vijaya — Oct 2023 check'),
    (2023, 10, 28,  96,  140,  5.5, 'manual', 'Festival season — controlled'),
    (2023, 11, 12,  94,  136,  5.5, 'manual', 'Back to normal'),
    (2023, 12,  8,  93,  135,  5.5, 'report', 'Vijaya — year-end panel'),

    # 2024 — Normal sustained
    (2024,  1, 18,  94,  136,  5.5, 'report', 'Vijaya — annual panel Jan 2024'),
    (2024,  3, 10,  93,  134,  5.4, 'report', 'Apollo — quarterly check'),
    (2024,  4, 22,  92,  133,  5.4, 'manual', 'Normal range — excellent'),
    (2024,  6, 15,  91,  131,  5.4, 'report', 'Vijaya — mid-year check'),
    (2024,  7, 10,  91,  130,  5.4, 'report', 'Apollo Hyderabad — Jul 2024'),
    (2024,  9,  8,  93,  135,  5.4, 'report', 'Thyrocare — quarterly'),
    (2024, 10, 15,  95,  138,  5.5, 'manual', 'Post-festival — slight rise'),
    (2024, 12, 20,  92,  132,  5.4, 'report', 'Vijaya — year-end 2024'),

    # 2025-2026 — Sustained excellent control
    (2025,  1,  8,  91,  131,  5.3, 'report', 'Vijaya — new year check'),
    (2025,  3, 20,  90,  130,  5.3, 'manual', 'Quarterly check'),
    (2025,  6, 12,  89,  128,  5.2, 'report', 'Apollo — mid-year 2025'),
    (2025,  9, 10,  91,  131,  5.3, 'report', 'Vijaya — Sep 2025'),
    (2025, 12,  5,  90,  129,  5.2, 'report', 'Vijaya — year-end 2025'),
    (2026,  1, 22,  91,  131,  5.3, 'report', 'Vijaya — Jan 2026'),
    (2026,  4,  8,  89,  128,  5.2, 'report', 'Vijaya — latest Apr 2026'),
]

# ── BMI data ─────────────────────────────────────────────────────────────────
bmi_data = [
    (2022,  1,  1, 162, 68.5, 'manual', 'Start of health journey'),
    (2022,  3,  1, 162, 67.8, 'manual', 'Slight improvement'),
    (2022,  6,  1, 162, 66.2, 'manual', '3-month progress'),
    (2022,  9,  1, 162, 65.0, 'manual', 'Consistent'),
    (2022, 12,  1, 162, 64.0, 'manual', 'Good progress'),
    (2023,  3,  1, 162, 63.2, 'manual', 'Entering normal range'),
    (2023,  6,  1, 162, 62.5, 'manual', 'Normal Weight achieved'),
    (2023,  9,  1, 162, 61.8, 'manual', 'Stable'),
    (2023, 12,  1, 162, 61.2, 'manual', 'Maintaining'),
    (2024,  3,  1, 162, 60.8, 'manual', 'Good control'),
    (2024,  6,  1, 162, 60.5, 'manual', 'Healthy range'),
    (2024,  9,  1, 162, 60.0, 'manual', 'Consistent'),
    (2024, 12,  1, 162, 59.8, 'manual', 'Year-end check'),
    (2025,  3,  1, 162, 59.5, 'manual', 'Stable'),
    (2025,  6,  1, 162, 59.2, 'manual', 'Consistent'),
    (2025,  9,  1, 162, 59.0, 'manual', 'Excellent'),
    (2025, 12,  1, 162, 58.9, 'manual', 'Best weight'),
    (2026,  3,  1, 162, 59.1, 'manual', 'Latest reading'),
]

# ── Seeder ───────────────────────────────────────────────────────────────────

def seed():
    with app.app_context():
        db.create_all()

        # Get or create user
        u = User.query.filter_by(email='esha@healthpulse.test').first()
        if not u:
            u = User(
                name='Ms. Esha',
                email='esha@healthpulse.test',
                password=generate_password_hash('test1234'),
                age=22, gender='Female', is_admin=False
            )
            db.session.add(u)
            db.session.flush()
            print(f"Created user: {u.name}")
        else:
            print(f"User exists: {u.name} — clearing old seeded data")
            Thyroid.query.filter_by(user_id=u.id).delete()
            BloodPressure.query.filter_by(user_id=u.id).delete()
            Diabetes.query.filter_by(user_id=u.id).delete()
            BMI.query.filter_by(user_id=u.id).delete()
            db.session.commit()

        uid = u.id

        # Thyroid
        for yr, mo, dy, tsh, t3, t4, src, note in thyroid_data:
            db.session.add(Thyroid(
                user_id=uid,
                tsh=jitter(tsh, .015), t3=jitter(t3, .02), t4=jitter(t4, .02),
                risk_level=risk_tsh(tsh), source=src, notes=note,
                recorded_at=dt(yr, mo, dy, random.choice([7,8,9,10]))
            ))

        # Blood Pressure
        for yr, mo, dy, sys, dia, pls, src, note in bp_data:
            db.session.add(BloodPressure(
                user_id=uid,
                systolic=ji(sys, 2), diastolic=ji(dia, 1), pulse=ji(pls, 3),
                risk_level=risk_bp(sys, dia), source=src, notes=note,
                recorded_at=dt(yr, mo, dy, random.choice([7,8,9,17,18,19]))
            ))

        # Blood Sugar
        for yr, mo, dy, fg, pp, a1c, src, note in diabetes_data:
            db.session.add(Diabetes(
                user_id=uid,
                fasting_glucose=jitter(fg, .01),
                postprandial_glucose=jitter(pp, .015),
                hba1c=round(a1c + random.uniform(-.04, .04), 1),
                risk_level=risk_dm(fg, a1c), source=src, notes=note,
                recorded_at=dt(yr, mo, dy, random.choice([7,8,9]))
            ))

        # BMI
        for yr, mo, dy, h, w, src, note in bmi_data:
            bv, cat, risk = calc_bmi(h, w)
            db.session.add(BMI(
                user_id=uid,
                height_cm=float(h),
                weight_kg=round(w + random.uniform(-.15, .15), 1),
                bmi_value=bv, category=cat, risk_level=risk,
                source=src, notes=note,
                recorded_at=dt(yr, mo, dy, 8)
            ))

        db.session.commit()

        print(f"\n✅ Seeded successfully for {u.name}:")
        print(f"   Thyroid readings    : {len(thyroid_data)}")
        print(f"   Blood Pressure      : {len(bp_data)}")
        print(f"   Blood Sugar         : {len(diabetes_data)}")
        print(f"   BMI entries         : {len(bmi_data)}")
        print(f"\n   Login  →  esha@healthpulse.test  |  test1234")
        print("\n── Data storyline ──────────────────────────────────────────")
        print("Thyroid : 60 readings | TSH 45.3 (Jan 2023) → 2.2 (2024-25)")
        print("          Levothyroxine started Apr 2023, normalised Feb 2024")
        print("BP      : 80 readings | 142/91 (2022) → 115/74 (2024)")
        print("          Stage 1 HTN → Normal with yoga + diet")
        print("Sugar   : 55 readings | 115 mg/dL (2022) → 89 mg/dL (2025)")
        print("          Pre-diabetic → Normal via low-GI diet")
        print("BMI     : 18 entries  | 68.5 kg (2022) → 59 kg (2025)")

if __name__ == '__main__':
    seed()