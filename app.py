"""
AI Medical Report Analyser — Flask Backend
Analyzes medical report PDFs using PyMuPDF for text extraction and
HuggingFace free Inference API (no API key needed) for AI analysis.
"""

import os
import json
import re
import sqlite3
import time
from functools import wraps

from flask import Flask, request, jsonify, session, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import fitz  # PyMuPDF
import requests as http_requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# Detect Vercel environment (read-only filesystem except /tmp)
IS_VERCEL = os.environ.get('VERCEL', False)

# Open Source Unified LLM Configuration
SAMBANOVA_API_KEY = os.getenv('SAMBANOVA_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
HF_API_TOKEN = os.getenv('HF_API_TOKEN', '')


# Upload directory — use /tmp on Vercel, local 'uploads/' in dev
if IS_VERCEL:
    UPLOAD_FOLDER = '/tmp/uploads'
else:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize the database
from database import init_db, get_db, close_db
init_db()
app.teardown_appcontext(close_db)

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


@app.route('/static/<path:filename>')
def static_files(filename):
    """Explicitly serve static files — required for Vercel deployment."""
    from flask import send_from_directory
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    return send_from_directory(static_dir, filename)

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
# PDF Text Extraction using PyMuPDF
# ---------------------------------------------------------------------------

def extract_text_from_pdf(filepath: str) -> str:
    """
    Extract all text from a PDF file using PyMuPDF.
    Handles scanned PDFs with embedded text, multi-page documents,
    and various PDF encodings.
    """
    doc = fitz.open(filepath)
    full_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            full_text.append(f"--- Page {page_num + 1} ---\n{text}")

    doc.close()

    extracted = "\n\n".join(full_text)

    if not extracted.strip():
        raise ValueError(
            "Could not extract text from this PDF. "
            "The file may be a scanned image without OCR text. "
            "Please use a PDF with selectable text."
        )

    return extracted

# ---------------------------------------------------------------------------
# Unified Open Source LLM API Caller
# ---------------------------------------------------------------------------

def call_llm_api(prompt: str, max_retries: int = 3) -> str:
    """
    Call a configured open-source LLM provider (SambaNova, Groq, OpenRouter, HuggingFace)
    using their OpenAI-compatible REST API endpoints.
    Automatically detects which keys are available in `.env` and uses the best one.
    """
    # 1. Retrieve API keys
    sambanova_key = os.getenv('SAMBANOVA_API_KEY', '').strip()
    groq_key = os.getenv('GROQ_API_KEY', '').strip()
    openrouter_key = os.getenv('OPENROUTER_API_KEY', '').strip()
    hf_token = os.getenv('HF_API_TOKEN', '').strip()

    # 2. Select Provider
    if sambanova_key and sambanova_key != 'your_sambanova_api_key_here':
        provider = 'SambaNova'
        url = "https://api.sambanova.ai/v1/chat/completions"
        model = "Llama-3.1-8B"  # Changed from DeepSeek-V3.1 to actual SambaNova model
        api_key = sambanova_key
    elif groq_key and groq_key != 'your_groq_api_key_here':
        provider = 'Groq'
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = "llama3-70b-8192"
        api_key = groq_key
    elif openrouter_key and openrouter_key != 'your_openrouter_api_key_here':
        provider = 'OpenRouter'
        url = "https://openrouter.ai/api/v1/chat/completions"
        model = "meta-llama/llama-3-8b-instruct:free"
        api_key = openrouter_key
    elif hf_token and hf_token != 'your_hf_token_here':
        provider = 'HuggingFace'
        url = "https://router.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1/v1/chat/completions"
        model = "mistralai/Mixtral-8x7B-Instruct-v0.1"
        api_key = hf_token
    else:
        raise ValueError(
            "NO_API_KEY: Please configure an open-source API provider key in your .env file. "
            "We support SambaNova (https://cloud.sambanova.ai/), Groq (https://console.groq.com/), "
            "or OpenRouter (https://openrouter.ai/)."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # OpenRouter requires extra headers
    if provider == 'OpenRouter':
        headers["HTTP-Referer"] = "https://github.com/Sudhangsahu2234/AI-Medical_Report_Analyser"
        headers["X-Title"] = "AI Medical Report Analyser"

    # Define fallback models for each provider
    fallbacks = {
        'SambaNova': ['Llama-3.1-8B', 'Llama-3.1-70B', 'Meta-Llama-3.3-70B-Instruct'],  # Updated fallbacks
        'Groq': ['llama-3.3-70b-versatile', 'llama3-70b-8192', 'mixtral-8x7b-32768'],
        'OpenRouter': ['meta-llama/llama-3-8b-instruct:free', 'mistralai/mistral-7b-instruct:free']
    }

    models_to_try = [model]
    if provider in fallbacks:
        for f_model in fallbacks[provider]:
            if f_model not in models_to_try:
                models_to_try.append(f_model)

    last_error = None
    for current_model in models_to_try:
        print(f"[INFO] Unified LLM: Requesting {provider} using model {current_model}...")

        payload = {
            "model": current_model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 6000,
            "response_format": {"type": "json_object"}
        }

        for attempt in range(max_retries):
            try:
                resp = http_requests.post(url, headers=headers, json=payload, timeout=90)

                # Handle 503 Model Loading (especially HuggingFace)
                if resp.status_code == 503 and attempt < max_retries - 1:
                    wait_time = 20
                    try:
                        error_data = resp.json()
                        wait_time = error_data.get("estimated_time", 20)
                    except Exception:
                        pass
                    print(f"[WARN] {provider} model is loading. Waiting {wait_time:.0f}s before retrying...")
                    time.sleep(min(wait_time, 45))
                    continue

                # Handle specific error status codes
                if resp.status_code == 401:
                    raise Exception(f"AUTH_ERROR: Unauthorized access. Please verify your {provider} API key in the `.env` file.")
                elif resp.status_code == 403:
                    raise Exception(f"FORBIDDEN: Access forbidden. Your {provider} API key might be suspended, restricted, or incorrect.")
                elif resp.status_code == 429:
                    if attempt < max_retries - 1:
                        print(f"[WARN] {provider} rate limited (429). Waiting 10s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(10)
                        continue
                    raise Exception(f"RATE_LIMIT: Rate limit or daily quota reached for {provider}.")
                elif resp.status_code == 400:
                    error_msg = resp.text
                    try:
                        error_json = resp.json()
                        error_msg = error_json.get("error", {}).get("message", resp.text)
                    except Exception:
                        pass
                    print(f"[WARN] {provider} returned 400 Bad Request for model {current_model}: {error_msg}")
                    last_error = Exception(f"BAD_REQUEST: {error_msg}")
                    break

                resp.raise_for_status()

                resp_json = resp.json()
                choices = resp_json.get("choices", [])
                if not choices:
                    raise Exception(f"Invalid API response: {resp_json}")

                return choices[0]["message"]["content"]

            except http_requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                last_error = Exception(f"CONNECTION_ERROR: Failed to connect to the {provider} API server. Please check your network connection.")
                break
            except http_requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                last_error = Exception(f"TIMEOUT: The request to {provider} timed out.")
                break
            except Exception as e:
                err_str = str(e)
                if any(k in err_str for k in ["AUTH_ERROR", "FORBIDDEN", "RATE_LIMIT", "CONNECTION_ERROR", "TIMEOUT"]):
                    raise
                if attempt < max_retries - 1:
                    print(f"[WARN] Attempt {attempt + 1} failed for model {current_model}: {err_str}. Retrying...")
                    time.sleep(5)
                    continue
                last_error = Exception(f"API_ERROR: {err_str}")

        print(f"[WARN] Model {current_model} failed. Trying next fallback model...")

    if last_error:
        raise last_error
    raise Exception("Failed to get response from AI after trying all fallback models.")


# ---------------------------------------------------------------------------
# Routes — Analysis
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = '''<s>[INST] You are an expert medical report analyst. Analyze the medical report text below and extract ALL test results.

Return ONLY a valid JSON object (no markdown, no explanation, no code fences). Use this exact structure:

{
  "patient_info": {
    "name": "Patient name or Not Available",
    "age": "Age or Not Available",
    "gender": "Gender or Not Available",
    "date": "Report date or Not Available",
    "lab_name": "Laboratory name or Not Available",
    "report_id": "Report ID or Not Available"
  },
  "readings": [
    {
      "test_name": "Name of the test",
      "category": "Category like Complete Blood Count, Lipid Profile, Liver Function, Kidney Function, Thyroid, Diabetes, Vitamins, Electrolytes, Urine Analysis etc",
      "value": "The measured value as string",
      "unit": "Unit of measurement",
      "normal_range": "Reference range",
      "status": "Normal or Abnormal",
      "flag": "Normal or High or Low or Critical High or Critical Low"
    }
  ],
  "abnormal_readings": [
    {
      "test_name": "Name of abnormal test",
      "value": "Measured value",
      "unit": "Unit",
      "normal_range": "Reference range",
      "flag": "High or Low or Critical High or Critical Low",
      "severity": "Mild or Moderate or Severe",
      "explanation": "Brief explanation of what this abnormal value means in simple language"
    }
  ],
  "recommendations": {
    "diet": [
      {"title": "Short title", "description": "Detailed dietary advice", "related_to": "Which abnormal reading"}
    ],
    "exercise": [
      {"title": "Short title", "description": "Exercise advice with duration", "related_to": "Which abnormal reading"}
    ],
    "lifestyle": [
      {"title": "Short title", "description": "Lifestyle changes", "related_to": "Which abnormal reading"}
    ],
    "medical_followup": [
      {"title": "Short title", "description": "Doctor consultation advice", "related_to": "Which abnormal reading"}
    ]
  },
  "summary": "3-5 sentence summary of overall health status from this report"
}

Rules:
1. Extract EVERY reading from the report
2. Be accurate with values and units
3. Use standard medical reference ranges if not in report
4. Return ONLY the JSON, nothing else
5. Empty categories should be empty arrays []

Here is the medical report text:

'''


@app.route('/api/analyze', methods=['POST'])
@login_required
def analyze():
    """
    Analyze an uploaded medical report PDF.
    Uses PyMuPDF for text extraction and HuggingFace for AI analysis.
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

    try:
        # --- Save file locally ---
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # --- Extract text from PDF using PyMuPDF ---
        pdf_text = extract_text_from_pdf(filepath)
        print(f"[INFO] Extracted {len(pdf_text)} characters from PDF")

        # Clean control characters to prevent serialization or API request errors
        pdf_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', pdf_text)

        # Truncate to fit model context window
        max_chars = 8000  # Reduced to leave more room for response
        if len(pdf_text) > max_chars:
            pdf_text = pdf_text[:max_chars] + "\n\n[... Report truncated ...]"

        # --- Build prompt and call Open Source LLM API ---
        full_prompt = ANALYSIS_PROMPT + pdf_text

        response_text = call_llm_api(full_prompt)
        print(f"[INFO] Got response ({len(response_text)} chars)")

        # --- Parse response JSON ---
        result = _parse_ai_response(response_text)

        # --- Save to database ---
        db = get_db()
        cursor = db.execute(
            'INSERT INTO analyses (user_id, filename, result_json) VALUES (?, ?, ?)',
            (session['user_id'], filename, json.dumps(result))
        )
        analysis_id = cursor.lastrowid
        db.commit()

        return jsonify({
            'success': True,
            'analysis': result,
            'analysis_id': analysis_id
        })

    except ValueError as e:
        # PDF extraction errors (e.g., scanned image without text)
        return jsonify({'error': str(e)}), 400

    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse AI response as JSON: {e}")
        print(f"[ERROR] Raw response: {response_text[:500] if 'response_text' in dir() else 'N/A'}")
        return jsonify({
            'error': 'The AI returned an invalid response. Please try again.'
        }), 500

    except Exception as e:
        error_msg = str(e)
        print(f"\n[ERROR] Analysis failed: {error_msg}\n")
        return jsonify({'error': f'Analysis failed: {error_msg}'}), 500

    finally:
        # --- Cleanup: delete local temp file ---
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


def _parse_ai_response(text: str) -> dict:
    """
    Parse the AI response text into a Python dict.
    Handles raw JSON, JSON in code fences, and JSON embedded in text.
    """
    if not text or not text.strip():
        raise json.JSONDecodeError("Empty response", "", 0)

    # Try to extract JSON from markdown code fences
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1).strip())

    # Try to find JSON object in the text (between first { and last })
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        return json.loads(brace_match.group(0))

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

    return jsonify({'message': 'Analysis deleted successfully'})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)