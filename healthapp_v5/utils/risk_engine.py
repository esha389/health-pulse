"""Rule-based risk classification using WHO/AHA medical reference ranges."""

def max_risk(a, b):
    order = {'Normal':0,'Low':1,'Medium':2,'High':3,'Critical':4}
    return a if order.get(a,0) >= order.get(b,0) else b

def classify_bp(systolic, diastolic):
    if systolic > 180 or diastolic > 120:
        return 'Critical','🚨 Hypertensive Crisis! Seek emergency care immediately.'
    elif systolic >= 140 or diastolic >= 90:
        return 'High','⚠️ Stage 2 Hypertension. Please consult a doctor promptly.'
    elif 130 <= systolic <= 139 or 80 <= diastolic <= 89:
        return 'Medium','⚡ Stage 1 Hypertension. Lifestyle changes needed.'
    elif 120 <= systolic <= 129 and diastolic < 80:
        return 'Low','🟡 Elevated BP. Monitor regularly and reduce salt intake.'
    else:
        return 'Normal','✅ Blood pressure is within normal range. Keep it up!'

def classify_diabetes(fasting=None, postprandial=None, hba1c=None):
    risk = 'Normal'; issues = []
    if fasting:
        if fasting >= 126:   risk='High';   issues.append(f'Fasting {fasting} mg/dL — Diabetic range')
        elif fasting >= 100: risk=max_risk(risk,'Medium'); issues.append(f'Fasting {fasting} mg/dL — Pre-diabetic')
        else: issues.append(f'Fasting {fasting} mg/dL — Normal')
    if postprandial:
        if postprandial >= 200:  risk='High'; issues.append(f'Post-meal {postprandial} — Diabetic range')
        elif postprandial >= 140: risk=max_risk(risk,'Medium'); issues.append(f'Post-meal {postprandial} — Pre-diabetic')
    if hba1c:
        if hba1c >= 6.5:  risk='High'; issues.append(f'HbA1c {hba1c}% — Diabetic range')
        elif hba1c >= 5.7: risk=max_risk(risk,'Medium'); issues.append(f'HbA1c {hba1c}% — Pre-diabetic')
    msgs = {'High':'🚨 Diabetic range detected. Consult an endocrinologist.',
            'Medium':'⚠️ Pre-diabetic values. Diet and exercise can reverse this!',
            'Normal':'✅ Blood sugar levels are healthy. Keep up the good work!'}
    return risk, msgs[risk], issues

def classify_thyroid(tsh=None, t3=None, t4=None):
    risk = 'Normal'; issues = []
    if tsh is not None:
        if tsh > 10 or tsh < 0.1:    risk='High'; issues.append(f'TSH {tsh} — severely abnormal')
        elif tsh > 4.78 or tsh < 0.4: risk=max_risk(risk,'Medium'); issues.append(f'TSH {tsh} — outside normal (0.55–4.78)')
        else: issues.append(f'TSH {tsh} — Normal')
    if t3 is not None:
        if t3 < 0.3 or t3 > 3.0: risk=max_risk(risk,'Medium'); issues.append(f'T3 {t3} — outside range')
    if t4 is not None:
        if t4 < 2.0 or t4 > 15: risk=max_risk(risk,'Medium'); issues.append(f'T4 {t4} — outside range')
    msgs = {'High':'🚨 Significant thyroid abnormality. See a doctor immediately.',
            'Medium':'⚠️ Thyroid levels slightly off. Follow-up needed.',
            'Normal':'✅ Thyroid function appears normal.'}
    return risk, msgs[risk], issues

def classify_bmi(height_cm, weight_kg):
    bmi = round(weight_kg / (height_cm/100)**2, 1)
    if bmi < 18.5:   cat,risk,tip='Underweight','Medium','🍽️ Increase caloric intake with nutritious foods.'
    elif bmi < 25:   cat,risk,tip='Normal Weight','Normal','✅ Healthy weight! Maintain your current habits.'
    elif bmi < 30:   cat,risk,tip='Overweight','Medium','🏃 Regular exercise and balanced diet recommended.'
    elif bmi < 35:   cat,risk,tip='Obese Class I','High','⚠️ Please seek medical advice for a weight loss plan.'
    elif bmi < 40:   cat,risk,tip='Obese Class II','High','⚠️ Medical intervention strongly recommended.'
    else:            cat,risk,tip='Obese Class III','Critical','🚨 Immediate medical attention required.'
    return bmi, cat, risk, tip

def overall_risk(risks):
    order = {'Normal':0,'Low':1,'Medium':2,'High':3,'Critical':4}
    best = 'Normal'
    for r in risks:
        if r and order.get(r,0) > order.get(best,0): best = r
    return best
