"""
AI Medical Report Analyser — Flask Backend
Analyzes medical report PDFs using Google Gemini AI to extract readings,
identify abnormal values, and provide health recommendations.
"""

import os
import io
import json
import re
import sqlite3
import tempfile
from functools import wraps

from flask import Flask, request, jsonify, session, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google import genai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# Detect Vercel environment (read-only filesystem except /tmp)
IS_VERCEL = os.environ.get('VERCEL', False)

# Gemini AI client
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Upload directory — use /tmp on Vercel, local 'uploads/' in dev
if IS_VERCEL:
    UPLOAD_FOLDER = '/tmp/uploads'
else:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize the database
from database import init_db, get_db
init_db()

# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated

# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    """Serve the main single-page application."""
    return render_template('index.html')

# ---------------------------------------------------------------------------
# Routes — Authentication
# ---------------------------------------------------------------------------

@app.route('/api/signup', methods=['POST'])
def signup():
    """Register a new user account."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    # Validation
    if not username or not email or not password:
        return jsonify({'error': 'Username, email, and password are required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    password_hash = generate_password_hash(password)

    try:
        db = get_db()
        db.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        db.commit()

        # Fetch the newly created user id
        user = db.execute(
            'SELECT id FROM users WHERE username = ?', (username,)
        ).fetchone()
        db.close()

        session['user_id'] = user['id']
        session['username'] = username

        return jsonify({'message': 'Account created successfully', 'username': username}), 201

    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate an existing user."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    db = get_db()
    # Allow login with username OR email
    user = db.execute(
        'SELECT * FROM users WHERE username = ? OR email = ?',
        (username, username)
    ).fetchone()
    db.close()

    if user is None or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401

    session['user_id'] = user['id']
    session['username'] = user['username']

    return jsonify({'message': 'Logged in successfully', 'username': user['username']})


@app.route('/api/logout', methods=['POST'])
def logout():
    """Log the current user out."""
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/me', methods=['GET'])
def me():
    """Check current authentication status."""
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'username': session.get('username')})
    return jsonify({'logged_in': False, 'username': None})

# ---------------------------------------------------------------------------
# Routes — Analysis
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = '''You are an expert medical report analyst. Analyze this medical report PDF thoroughly and extract ALL test results and readings.

Return your analysis as a JSON object with this EXACT structure (no markdown, no code fences, just raw JSON):

{
  "patient_info": {
    "name": "Patient name or 'Not Available'",
    "age": "Age or 'Not Available'",
    "gender": "Gender or 'Not Available'",
    "date": "Report date or 'Not Available'",
    "lab_name": "Laboratory name or 'Not Available'",
    "report_id": "Report/Sample ID or 'Not Available'"
  },
  "readings": [
    {
      "test_name": "Name of the test",
      "category": "Category (e.g., Complete Blood Count, Lipid Profile, Liver Function, Kidney Function, Thyroid, Diabetes, Vitamins, Electrolytes, Urine Analysis, etc.)",
      "value": "The measured value (number as string)",
      "unit": "Unit of measurement",
      "normal_range": "Reference/normal range",
      "status": "Normal" or "Abnormal",
      "flag": "Normal" or "High" or "Low" or "Critical High" or "Critical Low"
    }
  ],
  "abnormal_readings": [
    {
      "test_name": "Name of abnormal test",
      "value": "Measured value",
      "unit": "Unit",
      "normal_range": "Reference range",
      "flag": "High" or "Low" or "Critical High" or "Critical Low",
      "severity": "Mild" or "Moderate" or "Severe",
      "explanation": "Brief medical explanation of what this abnormal value means for health in simple language"
    }
  ],
  "recommendations": {
    "diet": [
      {
        "title": "Short recommendation title",
        "description": "Detailed dietary advice with specific foods to eat or avoid",
        "related_to": "Which abnormal reading this addresses"
      }
    ],
    "exercise": [
      {
        "title": "Short recommendation title",
        "description": "Specific exercise recommendations with duration and frequency",
        "related_to": "Which abnormal reading this addresses"
      }
    ],
    "lifestyle": [
      {
        "title": "Short recommendation title",
        "description": "Lifestyle changes like sleep, stress management, hydration etc.",
        "related_to": "Which abnormal reading this addresses"
      }
    ],
    "medical_followup": [
      {
        "title": "Short recommendation title",
        "description": "When to see a doctor, what specialist to consult, what additional tests to take",
        "related_to": "Which abnormal reading this addresses"
      }
    ]
  },
  "summary": "A comprehensive 3-5 sentence summary of the overall health status based on this report. Mention key concerns, positive findings, and general health outlook. Keep it encouraging but honest."
}

IMPORTANT RULES:
1. Extract EVERY single reading/test result from the report
2. Be accurate with values, units, and reference ranges
3. If a reading has no clear reference range in the report, use standard medical reference ranges
4. Provide actionable, specific recommendations (not generic advice)
5. Return ONLY the JSON object, no additional text
6. If recommendations categories have no items, use empty arrays []
7. For readings where status cannot be determined, mark as "Normal"'''


@app.route('/api/analyze', methods=['POST'])
@login_required
def analyze():
    """
    Analyze an uploaded medical report PDF using Google Gemini.
    Expects multipart/form-data with a 'file' field containing a PDF.
    """
    # --- Validate upload ---
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400

    filepath = None
    uploaded_file = None

    try:
        # --- Save file locally ---
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # --- Upload to Gemini ---
        uploaded_file = client.files.upload(
            file=filepath,
            config={'mime_type': 'application/pdf'}
        )

        # --- Send to Gemini for analysis ---
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[uploaded_file, ANALYSIS_PROMPT]
        )

        response_text = response.text

        # --- Parse response JSON ---
        result = _parse_gemini_response(response_text)

        # --- Save to database ---
        db = get_db()
        cursor = db.execute(
            'INSERT INTO analyses (user_id, filename, result_json) VALUES (?, ?, ?)',
            (session['user_id'], filename, json.dumps(result))
        )
        analysis_id = cursor.lastrowid
        db.commit()
        db.close()

        return jsonify({
            'success': True,
            'analysis': result,
            'analysis_id': analysis_id
        })

    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

    finally:
        # --- Cleanup: delete from Gemini servers ---
        if uploaded_file is not None:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass  # Best-effort cleanup

        # --- Cleanup: delete local temp file ---
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


def _parse_gemini_response(text: str) -> dict:
    """
    Parse the Gemini response text into a Python dict.
    Handles both raw JSON and JSON wrapped in markdown code fences.
    """
    # Try to extract JSON from markdown code fences first
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1).strip())

    # Fall back to parsing the raw text as JSON
    return json.loads(text.strip())

# ---------------------------------------------------------------------------
# Routes — History
# ---------------------------------------------------------------------------

@app.route('/api/history', methods=['GET'])
@login_required
def history():
    """Return a list of past analyses for the current user."""
    db = get_db()
    rows = db.execute(
        'SELECT id, filename, created_at FROM analyses WHERE user_id = ? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    db.close()

    return jsonify([
        {'id': row['id'], 'filename': row['filename'], 'created_at': row['created_at']}
        for row in rows
    ])


@app.route('/api/history/<int:analysis_id>', methods=['GET'])
@login_required
def get_analysis(analysis_id):
    """Return the full analysis result for a specific past analysis."""
    db = get_db()
    row = db.execute(
        'SELECT * FROM analyses WHERE id = ? AND user_id = ?',
        (analysis_id, session['user_id'])
    ).fetchone()
    db.close()

    if row is None:
        return jsonify({'error': 'Analysis not found'}), 404

    return jsonify({
        'id': row['id'],
        'filename': row['filename'],
        'analysis': json.loads(row['result_json']),
        'created_at': row['created_at']
    })


@app.route('/api/history/<int:analysis_id>', methods=['DELETE'])
@login_required
def delete_analysis(analysis_id):
    """Delete a specific past analysis."""
    db = get_db()
    db.execute(
        'DELETE FROM analyses WHERE id = ? AND user_id = ?',
        (analysis_id, session['user_id'])
    )
    db.commit()
    db.close()

    return jsonify({'message': 'Analysis deleted successfully'})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
