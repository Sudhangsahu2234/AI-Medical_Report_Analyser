# 🏥 AI Medical Report Analyser

An intelligent web application that analyzes medical report PDFs using **Google Gemini AI** to extract test results, identify abnormal readings, and provide personalized health recommendations.

---

## ✨ Features

- **PDF Analysis** — Upload any medical report PDF and get a comprehensive breakdown
- **Smart Extraction** — Automatically extracts all test results, values, units, and reference ranges
- **Abnormal Detection** — Identifies out-of-range readings with severity classification (Mild / Moderate / Severe)
- **Health Recommendations** — Personalized diet, exercise, lifestyle, and medical follow-up advice
- **User Accounts** — Secure signup/login with hashed passwords
- **Analysis History** — View, revisit, and delete past analyses
- **RESTful API** — Clean JSON API for frontend integration

---

## 📋 Prerequisites

- **Python 3.8+**
- A free **Google Gemini API key** (see setup step 4)

---

## 🚀 Setup Instructions

### 1. Clone or Download the Project

```bash
git clone <repository-url>
cd AI-Medical-Report-Analyser
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a Free Gemini API Key

1. Go to [https://aistudio.google.com](https://aistudio.google.com)
2. Sign in with your Google account
3. Navigate to **API Keys** and create a new key
4. Copy the key

### 5. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env and replace the placeholder with your actual key
GEMINI_API_KEY=your_actual_api_key_here
```

### 6. Run the Application

```bash
python app.py
```

### 7. Open in Browser

Navigate to [http://localhost:5000](http://localhost:5000)

---

## 🛠️ Tech Stack

| Layer        | Technology                        |
| ------------ | --------------------------------- |
| Backend      | Python, Flask                     |
| AI Engine    | Google Gemini 2.0 Flash           |
| Database     | SQLite                            |
| Auth         | Session-based, Werkzeug hashing   |
| API Style    | RESTful JSON                      |

---

## 📁 Project Structure

```
AI-Medical Report Analyser/
├── app.py              # Main Flask application & API routes
├── database.py         # SQLite database setup & helpers
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .env                # Your actual API key (git-ignored)
├── .gitignore          # Git ignore rules
├── README.md           # This file
├── templates/          # HTML templates
│   └── index.html      # Single-page frontend
└── uploads/            # Temporary PDF storage (git-ignored)
```

---

## 🔒 API Endpoints

| Method   | Endpoint                      | Auth | Description                  |
| -------- | ----------------------------- | ---- | ---------------------------- |
| `GET`    | `/`                           | No   | Serve the frontend           |
| `POST`   | `/api/signup`                 | No   | Create a new account         |
| `POST`   | `/api/login`                  | No   | Log in                       |
| `POST`   | `/api/logout`                 | No   | Log out                      |
| `GET`    | `/api/me`                     | No   | Check auth status            |
| `POST`   | `/api/analyze`                | Yes  | Upload & analyze a PDF       |
| `GET`    | `/api/history`                | Yes  | List past analyses           |
| `GET`    | `/api/history/<id>`           | Yes  | Get a specific analysis      |
| `DELETE` | `/api/history/<id>`           | Yes  | Delete an analysis           |

---

## ⚠️ Disclaimer

> This application is for **informational and educational purposes only**. It is **not** a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider for medical decisions. The AI-generated analysis may contain inaccuracies and should not be relied upon for clinical use.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
