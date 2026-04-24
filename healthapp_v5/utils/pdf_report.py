"""Generate a nicely formatted health summary PDF."""
from fpdf import FPDF
from datetime import datetime
import os

class HealthPDF(FPDF):
    def header(self):
        self.set_fill_color(15, 76, 117)
        self.rect(0, 0, 210, 28, 'F')
        self.set_font('Helvetica','B',18)
        self.set_text_color(255,255,255)
        self.cell(0,14,'HealthTrack Pro',ln=True,align='C')
        self.set_font('Helvetica','',9)
        self.cell(0,8,'Personal Health Summary Report',ln=True,align='C')
        self.set_text_color(0,0,0)
        self.ln(3)

    def footer(self):
        self.set_y(-14)
        self.set_font('Helvetica','I',8)
        self.set_text_color(130,130,130)
        self.cell(0,10,f'Generated {datetime.now().strftime("%d %b %Y %H:%M")}  |  Page {self.page_no()}',align='C')

    def sec(self, title, r=15, g=76, b=117):
        self.set_fill_color(r,g,b)
        self.set_text_color(255,255,255)
        self.set_font('Helvetica','B',11)
        self.cell(0,8,f'  {title}',ln=True,fill=True)
        self.set_text_color(0,0,0)
        self.ln(1)

    def row(self, label, value, risk=None):
        self.set_font('Helvetica','B',9)
        self.set_fill_color(245,248,252)
        self.cell(65,7,f'  {label}',border=1,fill=True)
        self.set_font('Helvetica','',9)
        self.cell(85,7,f'  {value}',border=1)
        if risk:
            colors={'Normal':(34,197,94),'Low':(163,230,53),'Medium':(251,191,36),'High':(239,68,68),'Critical':(127,29,29)}
            c=colors.get(risk,(150,150,150))
            self.set_fill_color(*c); self.set_text_color(255,255,255)
            self.cell(40,7,f'  {risk}',border=1,fill=True)
            self.set_text_color(0,0,0)
        self.ln()

def generate(user, bp_recs, dm_recs, th_recs, bmi_recs, ai_text=None):
    pdf = HealthPDF()
    pdf.add_page(); pdf.set_auto_page_break(auto=True,margin=14)

    pdf.sec('Patient Information')
    pdf.row('Name', user.name)
    pdf.row('Age', f'{user.age} years' if user.age else 'N/A')
    pdf.row('Gender', user.gender or 'N/A')
    pdf.row('Report Date', datetime.now().strftime('%d %B %Y'))
    pdf.ln(4)

    for title, recs, color, fmt in [
        ('Blood Pressure Records',(30,100,160), bp_recs,
         lambda r: (f'{r.systolic}/{r.diastolic} mmHg | Pulse: {r.pulse or "N/A"} bpm', r.risk_level)),
        ('Diabetes Records',(20,130,80), dm_recs,
         lambda r: (' | '.join(filter(None,[f'Fasting: {r.fasting_glucose} mg/dL' if r.fasting_glucose else None, f'HbA1c: {r.hba1c}%' if r.hba1c else None])) or 'N/A', r.risk_level)),
        ('Thyroid Records',(100,40,140), th_recs,
         lambda r: (' | '.join(filter(None,[f'TSH:{r.tsh}' if r.tsh else None, f'T3:{r.t3}' if r.t3 else None, f'T4:{r.t4}' if r.t4 else None])) or 'N/A', r.risk_level)),
        ('BMI Records',(180,80,20), bmi_recs,
         lambda r: (f'BMI:{r.bmi_value} | {r.category} | {r.weight_kg}kg/{r.height_cm}cm', r.risk_level)),
    ]:
        pdf.sec(title, *color)
        recs_list = list(recs)
        if recs_list:
            for rec in recs_list[:5]:
                val, risk = fmt(rec)
                pdf.row(rec.recorded_at.strftime('%d %b %Y'), val, risk)
        else:
            pdf.set_font('Helvetica','I',9); pdf.cell(0,7,'  No records found.',ln=True)
        pdf.ln(3)

    if ai_text:
        pdf.add_page()
        pdf.sec('AI-Powered Health Insights (Claude AI)')
        pdf.set_font('Helvetica','',9)
        pdf.multi_cell(0,5,ai_text.replace('**','').replace('#','').replace('*',''))
        pdf.ln(3)

    pdf.set_fill_color(255,243,205); pdf.set_text_color(100,70,0)
    pdf.set_font('Helvetica','I',8)
    pdf.multi_cell(0,5,'  ⚠ Disclaimer: For informational purposes only. Not a substitute for professional medical advice.',fill=True)

    os.makedirs('static/reports',exist_ok=True)
    path = f'static/reports/report_{user.id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.pdf'
    pdf.output(path)
    return path
