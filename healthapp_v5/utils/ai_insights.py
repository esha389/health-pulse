"""
Health Insights — works offline by default, uses Gemini if key provided.
"""
import json


# ── Offline rule-based insights ───────────────────────────────────────────────

def _offline_insights(user_data: dict) -> str:
    """Generate structured health insights without any API."""
    name = user_data.get('name', 'you')
    age  = user_data.get('age')
    bp   = user_data.get('blood_pressure', {})
    dm   = user_data.get('diabetes', {})
    th   = user_data.get('thyroid', {})
    bmi  = user_data.get('bmi', {})

    concerns = []
    recs     = []
    tips     = []
    see_doc  = []

    # ── Thyroid ──────────────────────────────────────────────────────────────
    tsh = th.get('tsh')
    if tsh:
        if tsh > 4.78:
            level = "significantly elevated" if tsh > 10 else "elevated"
            concerns.append(f"TSH is {level} at {tsh} µIU/mL (normal: 0.55–4.78), indicating an **underactive thyroid (Hypothyroidism)**.")
            recs.append("Take thyroid medication (levothyroxine) exactly as prescribed — same time daily, ideally on an empty stomach.")
            tips.append("Avoid raw cruciferous vegetables (cabbage, broccoli) in large amounts — they can affect thyroid function.")
            see_doc.append("See an endocrinologist to discuss thyroid hormone replacement therapy.")
        elif tsh < 0.55:
            concerns.append(f"TSH is low at {tsh} µIU/mL — this suggests an **overactive thyroid (Hyperthyroidism)**.")
            recs.append("Avoid caffeine and stimulants which can worsen palpitations.")
            see_doc.append("Consult an endocrinologist promptly for hyperthyroidism evaluation.")
        elif th.get('risk') == 'Normal':
            tips.append("Thyroid levels are normal — schedule a recheck in 6–12 months.")

    # ── Blood Pressure ────────────────────────────────────────────────────────
    sys_ = bp.get('systolic'); dia_ = bp.get('diastolic')
    bp_risk = bp.get('risk', 'Normal')
    if bp_risk in ('High', 'Critical'):
        concerns.append(f"Blood pressure {sys_}/{dia_} mmHg is in the **{bp_risk}** range.")
        recs.append("Reduce salt intake to under 5g/day and avoid processed foods.")
        recs.append("Walk for 30 minutes daily — this alone can lower BP by 5–8 mmHg.")
        see_doc.append("Visit your doctor to discuss blood pressure medication if lifestyle changes aren't enough.")
    elif bp_risk == 'Medium':
        recs.append("Monitor blood pressure daily and reduce stress with deep breathing or yoga.")

    # ── Diabetes ─────────────────────────────────────────────────────────────
    fg = dm.get('fasting'); a1c = dm.get('hba1c')
    dm_risk = dm.get('risk', 'Normal')
    if dm_risk == 'High':
        concerns.append(f"Blood sugar is in the **diabetic range** (fasting: {fg or 'N/A'} mg/dL, HbA1c: {a1c or 'N/A'}%).")
        recs.append("Follow a low-GI diet — replace white rice/bread with millets, oats, or brown rice.")
        recs.append("Walk 30 minutes after meals to control post-meal blood sugar spikes.")
        see_doc.append("Consult your diabetologist for a medication and diet plan.")
    elif dm_risk == 'Medium':
        concerns.append("Blood sugar is in the **pre-diabetic range** — this is reversible with lifestyle changes.")
        recs.append("Cut sugar, maida (refined flour), and sugary drinks from your diet completely.")
        tips.append("Losing even 5% of body weight can significantly improve blood sugar control.")

    # ── BMI ───────────────────────────────────────────────────────────────────
    bmi_val = bmi.get('value'); bmi_cat = bmi.get('category', '')
    if bmi_val:
        if bmi_val >= 30:
            concerns.append(f"BMI {bmi_val} falls in the **{bmi_cat}** category.")
            recs.append("Aim for 150 minutes of moderate exercise per week — start with brisk walking.")
            see_doc.append("Ask your doctor about a supervised weight management plan.")
        elif bmi_val >= 25:
            tips.append(f"BMI {bmi_val} (Overweight) — even a 5–10% weight reduction significantly improves health markers.")
        elif bmi_val < 18.5:
            concerns.append(f"BMI {bmi_val} indicates **Underweight** — ensure adequate protein and caloric intake.")

    # ── Age-specific tips ─────────────────────────────────────────────────────
    if age:
        if int(age) > 40:
            tips.append("After 40, annual health checkups including thyroid, blood sugar, and lipids are recommended.")
        if int(age) < 30:
            tips.append("Young age is the best time to build healthy habits — exercise and diet now protect you for decades.")

    # ── General tips ─────────────────────────────────────────────────────────
    tips += [
        "Drink 8–10 glasses of water daily.",
        "Sleep 7–8 hours — poor sleep worsens blood sugar, BP, and thyroid function.",
        "Regular meditation or deep breathing reduces cortisol, which affects all these conditions.",
    ]

    # ── Build the formatted output ────────────────────────────────────────────
    overall = "good" if not concerns else ("concerning in some areas" if len(concerns) == 1 else "needs attention in multiple areas")

    lines = [
        f"## 1. Overall Health Summary",
        f"Hi {name}! Your overall health is **{overall}**. "
        + ("Keep up the great work!" if not concerns else "Here's a focused breakdown to help you take action."),
        "",
        "## 2. Key Concerns",
    ]
    if concerns:
        for c in concerns:
            lines.append(f"- {c}")
    else:
        lines.append("- No critical concerns identified from your latest readings. Great job! 🎉")

    lines += ["", "## 3. Personalized Recommendations"]
    for r in (recs or ["Maintain your current healthy lifestyle — you're doing well!"]):
        lines.append(f"- {r}")

    lines += ["", "## 4. Lifestyle Tips"]
    for t in tips[:4]:
        lines.append(f"- {t}")

    lines += ["", "## 5. When to See a Doctor"]
    if see_doc:
        for s in see_doc:
            lines.append(f"- {s}")
    else:
        lines.append("- Schedule a routine checkup every 6–12 months to stay ahead of any changes.")

    lines += ["", "---", "_Keep tracking your health consistently — every reading brings you closer to better wellbeing!_ 💚"]
    return '\n'.join(lines)


# ── Gemini fallback (only if key provided) ────────────────────────────────────

def _gemini_insights(user_data: dict, api_key: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""You are a supportive health assistant. Analyse this patient data and write a warm, 
practical health analysis under 400 words using these exact headings:
## 1. Overall Health Summary
## 2. Key Concerns
## 3. Personalized Recommendations
## 4. Lifestyle Tips
## 5. When to See a Doctor

Patient Data:
{json.dumps(user_data, indent=2)}"""
    response = model.generate_content(prompt)
    return response.text


# ── Public API ────────────────────────────────────────────────────────────────

def get_insights(user_data: dict, api_key: str = '') -> str:
    """
    Generate health insights. 
    - If api_key is provided: tries Gemini first, falls back to offline.
    - If no api_key: generates offline insights (always works, no quota).
    """
    if api_key and api_key.strip() and api_key.strip() not in ('YOUR_GEMINI_API_KEY_HERE', ''):
        try:
            return _gemini_insights(user_data, api_key.strip())
        except Exception as e:
            print(f"[ai_insights] Gemini failed ({e}), using offline insights")
    return _offline_insights(user_data)
