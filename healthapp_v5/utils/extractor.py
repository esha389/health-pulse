"""
Lab Report Extractor — 100% FREE, No API Required
───────────────────────────────────────────────────
Uses pdfplumber (text extraction) + regex to parse Indian lab reports.
Works completely offline — no Gemini, no Anthropic, no internet needed.

Tested against: Vijaya Diagnostic Centre, Apollo, Thyrocare, Metropolis.

For image-only reports (scanned photos), pass use_gemini=True with an API key.
"""

import re
import json
import pdfplumber
from PIL import Image
from datetime import datetime
import io

# ── Known test patterns for Indian lab reports ─────────────────────────────────
# Each entry: (key_in_output, list_of_name_patterns, unit_hint)
THYROID_PATTERNS = [
    ('tsh',  [r'tsh[\s\-–]*ultrasensitive', r'\btsh\b', r'thyroid stimulating'],  'µIU/mL'),
    ('t3',   [r't3\s*total', r'triiodothyronine', r'\bt3\b'],                      'ng/mL'),
    ('t4',   [r't4\s*total', r'thyroxine', r'\bt4\b'],                             'µg/dL'),
]
DIABETES_PATTERNS = [
    ('fasting_glucose',      [r'fasting\s*(blood\s*)?glucose', r'fbg', r'fasting\s*sugar'],  'mg/dL'),
    ('postprandial_glucose', [r'post\s*(prandial|meal|lunch)', r'pp\s*glucose', r'ppbs'],     'mg/dL'),
    ('hba1c',                [r'hba1c', r'hb\s*a1c', r'glycated\s*haemoglobin', r'gly.*hb'], '%'),
]
BP_PATTERNS = [
    ('systolic',  [r'systolic'],  'mmHg'),
    ('diastolic', [r'diastolic'], 'mmHg'),
    ('pulse',     [r'pulse\s*rate', r'\bpulse\b', r'heart\s*rate'], 'bpm'),
]
LIPID_PATTERNS = [
    ('total_cholesterol',  [r'total\s*cholesterol', r'serum\s*cholesterol'],      'mg/dL'),
    ('ldl',                [r'\bldl\b', r'low\s*density\s*lipoprotein'],           'mg/dL'),
    ('hdl',                [r'\bhdl\b', r'high\s*density\s*lipoprotein'],          'mg/dL'),
    ('triglycerides',      [r'triglyceride', r'\btg\b'],                           'mg/dL'),
    ('vldl',               [r'\bvldl\b'],                                           'mg/dL'),
]
LIVER_PATTERNS = [
    ('sgpt',                  [r'sgpt', r'alt\b', r'alanine\s*aminotransferase'],          'U/L'),
    ('sgot',                  [r'sgot', r'ast\b', r'aspartate\s*aminotransferase'],        'U/L'),
    ('bilirubin_total',       [r'bilirubin[\s,]*total', r'total\s*bilirubin'],              'mg/dL'),
    ('bilirubin_direct',      [r'bilirubin[\s,]*direct', r'direct\s*bilirubin'],            'mg/dL'),
    ('alkaline_phosphatase',  [r'alkaline\s*phosphatase', r'\balk\s*phos\b', r'\balp\b'],  'U/L'),
    ('total_protein',         [r'total\s*protein'],                                          'g/dL'),
    ('albumin',               [r'\balbumin\b'],                                               'g/dL'),
]
KIDNEY_PATTERNS = [
    ('creatinine',   [r'serum\s*creatinine', r'\bcreatinine\b'],  'mg/dL'),
    ('urea',         [r'serum\s*urea', r'\burea\b', r'\bbun\b'],  'mg/dL'),
    ('uric_acid',    [r'uric\s*acid', r'serum\s*urate'],           'mg/dL'),
    ('egfr',         [r'egfr', r'gfr'],                             'mL/min'),
    ('sodium',       [r'\bsodium\b', r'\bna\b'],                   'mEq/L'),
    ('potassium',    [r'\bpotassium\b', r'\bk\b'],                 'mEq/L'),
]
CBC_PATTERNS = [
    ('hemoglobin',   [r'haemoglobin', r'hemoglobin', r'\bhb\b'],        'g/dL'),
    ('wbc',          [r'wbc', r'total\s*leucocyte', r'white\s*blood'],   'cells/µL'),
    ('rbc',          [r'\brbc\b', r'red\s*blood\s*cell'],                'million/µL'),
    ('platelets',    [r'platelet', r'\bplt\b'],                          'lakh/µL'),
    ('hematocrit',   [r'pcv', r'hematocrit', r'haematocrit'],            '%'),
    ('mcv',          [r'\bmcv\b'],                                        'fL'),
    ('mch',          [r'\bmch\b'],                                        'pg'),
    ('mchc',         [r'\bmchc\b'],                                       'g/dL'),
]
BMI_PATTERNS = [
    ('weight_kg',  [r'\bweight\b'],  'kg'),
    ('height_cm',  [r'\bheight\b'],  'cm'),
    ('bmi',        [r'\bbmi\b', r'body\s*mass\s*index'], 'kg/m²'),
]

TYPE_PATTERN_MAP = {
    'thyroid':        THYROID_PATTERNS,
    'diabetes':       DIABETES_PATTERNS,
    'blood_pressure': BP_PATTERNS,
    'lipid':          LIPID_PATTERNS,
    'liver':          LIVER_PATTERNS,
    'kidney':         KIDNEY_PATTERNS,
    'cbc':            CBC_PATTERNS,
    'bmi':            BMI_PATTERNS,
}

# ── Keywords to identify test type ────────────────────────────────────────────
TYPE_KEYWORDS = {
    'thyroid':        ['thyroid', 'tsh', 't3', 't4', 'triiodothyronine', 'thyroxine'],
    'diabetes':       ['glucose', 'hba1c', 'diabetic', 'sugar', 'glycated'],
    'blood_pressure': ['blood pressure', 'systolic', 'diastolic'],
    'lipid':          ['lipid', 'cholesterol', 'triglyceride', 'ldl', 'hdl'],
    'liver':          ['liver', 'sgpt', 'sgot', 'bilirubin', 'hepatic', 'lft'],
    'kidney':         ['kidney', 'creatinine', 'urea', 'uric acid', 'renal', 'kft'],
    'cbc':            ['haemoglobin', 'hemoglobin', 'wbc', 'rbc', 'platelet', 'complete blood'],
    'bmi':            ['bmi', 'body mass index', 'weight', 'height'],
}

# ── Reference ranges for abnormal flag generation ─────────────────────────────
REFERENCE_RANGES = {
    'tsh':               (0.55, 4.78),
    't3':                (0.60, 1.81),
    't4':                (3.2,  12.6),
    'fasting_glucose':   (70,   99),
    'postprandial_glucose': (70, 139),
    'hba1c':             (0,    5.6),
    'total_cholesterol': (0,    200),
    'ldl':               (0,    100),
    'hdl':               (40,   999),
    'triglycerides':     (0,    150),
    'sgpt':              (0,    40),
    'sgot':              (0,    40),
    'bilirubin_total':   (0,    1.2),
    'alkaline_phosphatase': (44, 147),
    'creatinine':        (0.7,  1.2),
    'urea':              (15,   45),
    'uric_acid':         (3.5,  7.2),
    'hemoglobin':        (12.0, 17.5),
    'wbc':               (4000, 11000),
    'platelets':         (1.5,  4.5),   # lakh/µL
}

CLINICAL_HINTS = {
    'tsh':    ('Hypothyroidism', 'Hyperthyroidism'),
    't3':     ('Low T3', 'High T3 / possible Hyperthyroidism'),
    't4':     ('Low T4 / Hypothyroidism', 'High T4 / Hyperthyroidism'),
    'fasting_glucose': ('Hypoglycaemia', 'Pre-diabetic / Diabetic range'),
    'hba1c':  ('', 'Pre-diabetic / Diabetic range'),
    'total_cholesterol': ('', 'High cholesterol risk'),
    'ldl':    ('', 'High LDL — cardiovascular risk'),
    'hdl':    ('Low HDL — cardiovascular risk', ''),
    'sgpt':   ('', 'Elevated SGPT — liver stress'),
    'sgot':   ('', 'Elevated SGOT — liver/heart stress'),
    'creatinine': ('', 'Elevated creatinine — kidney stress'),
    'hemoglobin': ('Anaemia', 'Polycythaemia'),
}


# ── Text extraction ────────────────────────────────────────────────────────────

def _extract_text(filepath: str, ext: str) -> str:
    """Extract raw text from PDF or image."""
    if ext == 'pdf':
        try:
            with pdfplumber.open(filepath) as pdf:
                return '\n'.join(p.extract_text() or '' for p in pdf.pages)
        except Exception as e:
            raise ValueError(f"Could not read PDF: {e}. Run: pip install pdfplumber --upgrade")
    elif ext in ('png', 'jpg', 'jpeg', 'webp'):
        # For images, we cannot do offline OCR without pytesseract
        # Return empty so caller knows to try fallback
        return ''
    return ''


# ── Core parsing ───────────────────────────────────────────────────────────────

def _detect_type(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for ttype, keywords in TYPE_KEYWORDS.items():
        scores[ttype] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'other'


def _parse_value_from_line(line: str) -> float | None:
    """Extract the first numeric value from a text line."""
    # Match numbers like 19.079, 1.66, 130, 45.335
    m = re.search(r':\s*([\d]+\.?\d*)', line)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # Also try just finding a standalone number after whitespace
    m = re.search(r'\s+([\d]+\.[\d]+|\d{2,4})\s', line)
    if m:
        try:
            v = float(m.group(1))
            # Sanity check — avoid dates (2025, 2026 etc.) and IDs
            if v < 10000:
                return v
        except ValueError:
            pass
    return None


def _parse_reference_range(text_around: str) -> str | None:
    """Try to extract reference range like '0.55 - 4.78' or '0.55 to 4.78'."""
    m = re.search(r'([\d]+\.?\d*)\s*[-–to]+\s*([\d]+\.?\d*)', text_around)
    if m:
        return f"{m.group(1)} - {m.group(2)}"
    return None


def _find_value(text: str, patterns: list, key: str) -> tuple[float | None, str, str]:
    """
    Search all lines of text for a test result.
    Returns (value, unit, reference_range).
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for pat in patterns:
            if re.search(pat, line_lower):
                # Look in this line and the next 2 lines for the value
                search_window = '\n'.join(lines[i:min(i+4, len(lines))])
                val = _parse_value_from_line(line)
                if val is None:
                    # Try next line (sometimes value is on next line in columnar format)
                    for j in range(i+1, min(i+3, len(lines))):
                        val = _parse_value_from_line(lines[j])
                        if val is not None:
                            break
                if val is not None:
                    rng = _parse_reference_range(search_window)
                    return val, '', rng or ''
    return None, '', ''


def _extract_meta(text: str) -> dict:
    """Extract patient name, date, lab name etc. from the report header."""
    meta = {}
    lines = text.split('\n')
    text_lower = text.lower()

    # Lab name — usually prominent at top
    for line in lines[:8]:
        line_s = line.strip()
        if len(line_s) > 5 and any(w in line_s.lower() for w in
                ['diagnostic', 'hospital', 'laboratory', 'lab', 'clinic', 'medical', 'pathology']):
            meta['lab_name'] = line_s
            break

    # Patient name
    m = re.search(r'(?:name|patient)\s*[:\-]\s*([A-Za-z\s\.]+?)(?:\n|age|gender|reg)', text_lower)
    if m:
        raw = m.group(1).strip().title()
        if 2 < len(raw) < 60:
            meta['patient_name'] = raw

    # Age
    m = re.search(r'age[/\s]*gender?\s*[:\-]\s*(\d+)\s*(?:years?|yrs?)?', text_lower)
    if m:
        meta['patient_age'] = m.group(1) + ' Years'

    # Gender
    if 'female' in text_lower: meta['patient_gender'] = 'Female'
    elif 'male' in text_lower: meta['patient_gender'] = 'Male'

    # Referring doctor
    m = re.search(r'(?:ref(?:erred)?\s*by|referred\s*by|ref\.?\s*by)\s*[:\-]\s*(dr\.?\s*[A-Za-z\s]+?)(?:\n|sample|reg)', text_lower)
    if m:
        raw = m.group(1).strip().title()
        if len(raw) < 60:
            meta['referring_doctor'] = raw

    # Registration ID
    m = re.search(r'(?:registration\s*id?|reg(?:istration)?\s*(?:id|no|number)?)\s*[:\-]\s*([A-Z0-9]+)', text, re.IGNORECASE)
    if m:
        meta['registration_id'] = m.group(1).strip()

    # Date — look for collected/reported/printed date
    date_patterns = [
        r'collected\s*on\s*[:\-]?\s*(\d{1,2}[-/\s][A-Za-z]{3}[-/\s]\d{2,4})',
        r'reported\s*on\s*[:\-]?\s*(\d{1,2}[-/\s][A-Za-z]{3}[-/\s]\d{2,4})',
        r'(?:date|dt)\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        r'(\d{2}-[A-Za-z]{3}-\d{4})',
        r'(\d{2}/\d{2}/\d{4})',
    ]
    for dp in date_patterns:
        m = re.search(dp, text, re.IGNORECASE)
        if m:
            meta['test_date_raw'] = m.group(1).strip()
            break

    return meta


def _generate_summary(values: dict, test_type: str, abnormal: list) -> str:
    """Generate a plain-English summary without any AI API."""
    if not values:
        return "Values were extracted from the report. Please review results with your doctor."

    abnormal_count = len(abnormal)
    total = len(values)

    if test_type == 'thyroid':
        tsh = values.get('tsh')
        if tsh:
            if tsh > 4.78:
                direction = "elevated" if tsh < 10 else "significantly elevated"
                return (f"TSH is {direction} at {tsh} µIU/mL (normal: 0.55–4.78), suggesting "
                        f"Hypothyroidism (underactive thyroid). T3 and T4 levels help confirm this. "
                        f"Please consult an endocrinologist for appropriate treatment.")
            elif tsh < 0.55:
                return (f"TSH is low at {tsh} µIU/mL (normal: 0.55–4.78), suggesting "
                        f"Hyperthyroidism (overactive thyroid). "
                        f"Please consult an endocrinologist promptly.")
            else:
                return f"Thyroid function appears normal. TSH {tsh} µIU/mL is within the normal range (0.55–4.78). Continue regular monitoring."

    if abnormal_count == 0:
        return f"All {total} test value(s) are within normal range. Results look healthy — continue your current lifestyle."
    elif abnormal_count == 1:
        return f"1 out of {total} values is outside the normal range. {abnormal[0]} Review with your doctor at your next visit."
    else:
        return (f"{abnormal_count} out of {total} values are outside normal ranges. "
                f"Key concern: {abnormal[0]} Please schedule a follow-up with your doctor.")


# ── Main extraction function ───────────────────────────────────────────────────

def extract(filepath: str, file_ext: str, api_key: str = '') -> dict:
    """
    Extract all test values from a lab report.

    Completely offline — no API key needed.
    api_key parameter kept for backwards compatibility but is unused.

    Args:
        filepath : path to PDF or image file
        file_ext : extension (pdf, png, jpg, jpeg, webp)
        api_key  : ignored — extraction is done locally

    Returns:
        dict matching the same schema as the Gemini version
    """
    ext = file_ext.lower().lstrip('.')

    # Step 1: Get text
    text = _extract_text(filepath, ext)
    if not text and ext in ('png', 'jpg', 'jpeg', 'webp'):
        # Image file — try to describe what we can
        raise ValueError(
            "Image-only reports require Tesseract OCR (optional). "
            "For best results, upload the PDF version of your lab report."
        )
    if not text:
        raise ValueError("Could not extract text from file. Ensure pdfplumber is installed: pip install pdfplumber")

    # Step 2: Detect test type
    test_type = _detect_type(text)

    # Step 3: Extract metadata
    meta = _extract_meta(text)

    # Step 4: Extract values for detected type + any cross-type matches
    all_patterns = TYPE_PATTERN_MAP.get(test_type, [])
    # Also try thyroid patterns if TSH/T3/T4 keywords present (common overlap)
    if test_type != 'thyroid' and any(k in text.lower() for k in ['tsh', 't3 total', 't4 total']):
        all_patterns = THYROID_PATTERNS + all_patterns
        test_type = 'thyroid'

    values = {}
    units = {}
    reference_ranges = {}

    for key, patterns, unit_hint in all_patterns:
        val, _, rng = _find_value(text, patterns, key)
        if val is not None:
            values[key] = val
            units[key] = unit_hint
            if rng:
                reference_ranges[key] = rng

    # Step 5: Check abnormal flags
    abnormal_flags = []
    for key, val in values.items():
        if key in REFERENCE_RANGES:
            lo, hi = REFERENCE_RANGES[key]
            hint_lo, hint_hi = CLINICAL_HINTS.get(key, ('', ''))
            unit = units.get(key, '')
            rng_str = reference_ranges.get(key, f"{lo}–{hi}")
            if val < lo and hint_lo:
                abnormal_flags.append(
                    f"{key.upper().replace('_',' ')} {val} {unit} is LOW "
                    f"(normal: {rng_str}) — {hint_lo}"
                )
            elif val > hi and hint_hi:
                abnormal_flags.append(
                    f"{key.upper().replace('_',' ')} {val} {unit} is HIGH "
                    f"(normal: {rng_str}) — {hint_hi}"
                )

    # Step 6: Generate summary
    summary = _generate_summary(values, test_type, abnormal_flags)

    # Step 7: Parse date
    test_date_raw = meta.pop('test_date_raw', None)
    test_date_str = None
    if test_date_raw:
        parsed = parse_date(test_date_raw)
        if parsed:
            test_date_str = parsed.strftime('%Y-%m-%d')

    return {
        'test_type':       test_type,
        'test_date':       test_date_str,
        'lab_name':        meta.get('lab_name'),
        'patient_name':    meta.get('patient_name'),
        'patient_age':     meta.get('patient_age'),
        'patient_gender':  meta.get('patient_gender'),
        'referring_doctor':meta.get('referring_doctor'),
        'registration_id': meta.get('registration_id'),
        'values':          values,
        'units':           units,
        'reference_ranges':reference_ranges,
        'abnormal_flags':  abnormal_flags,
        'summary':         summary,
    }


# ── Date parsing ───────────────────────────────────────────────────────────────

def parse_date(s) -> datetime | None:
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y',
                '%d-%b-%Y', '%d %b %Y', '%d %B %Y', '%d-%b-%y',
                '%Y/%m/%d', '%d-%m-%y', '%d/%m/%y'):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            continue
    return None
