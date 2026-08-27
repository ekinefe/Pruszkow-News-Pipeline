# Pruszkow News Pipeline

Automated email-to-article pipeline for **pruszkowmowi.pl** - a Polish community news website.

Fetches emails from Gmail, generates Polish news articles using Google Gemini AI, and provides a web interface for management.

## Quick Start

### 1. Install Python dependencies

```bash
cd pruszkow-news-pipeline
pip install -r requirements.txt
```

### 2. Configure

Copy your Google OAuth credentials file to this directory:
```bash
cp /path/to/client_secret_*.json ./client_secret.json
```

Create a `.env` file (or copy the example):
```bash
cp .env.example .env
# Edit .env with your API key
```

### 3. Run

**Mac / Linux:**
```bash
./start.sh
```

**Windows:**
```bash
start.bat
```

**Or manually:**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open

Visit **http://localhost:8000** in your browser.

## First Run

On first launch, you'll need to authenticate with Gmail:
1. Go to the **Settings** tab
2. Click **Connect Gmail**
3. Complete the OAuth flow in your browser

## Features

- **Dashboard** - Overview of emails and articles
- **Email Manager** - Fetch, preview, and select emails
- **Article Generator** - AI-powered Polish news articles
- **Article Viewer** - Read, edit, and download articles
- **Settings** - Configure API keys and preferences

## Project Structure

```
pruszkow-news-pipeline/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── models.py            # Data models
│   ├── services/
│   │   ├── gmail.py         # Gmail API
│   │   ├── gemini.py        # AI generation
│   │   └── database.py      # Data storage
│   └── routes/
│       ├── emails.py        # Email endpoints
│       ├── articles.py      # Article endpoints
│       └── settings.py      # Config endpoints
├── frontend/
│   ├── index.html           # Main UI
│   ├── css/style.css        # Styles
│   └── js/
│       ├── api.js           # API client
│       └── app.js           # App logic
├── data/                    # Generated data
├── requirements.txt
├── .env.example
├── start.sh                 # Mac/Linux launcher
└── start.bat                # Windows launcher
```

## Security

- Never commit `client_secret*.json`, `token.json`, or `.env`
- These are all in `.gitignore` by default
- Revoke access at https://myaccount.google.com/permissions
