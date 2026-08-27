# Pruszkow News Pipeline

Automated email-to-article pipeline for **pruszkowmowi.pl** - a Polish community news website.

Fetches emails from Gmail, generates Polish news articles using Google Gemini AI, and provides a web interface for management.

---

## Table of Contents

- [What is This?](#what-is-this)
- [Requirements](#requirements)
- [Download](#download)
- [First-Time Setup](#first-time-setup)
  - [Windows](#windows-setup)
  - [macOS](#macos-setup)
  - [Linux](#linux-setup)
- [Starter Scripts Explained](#starter-scripts-explained)
- [First Launch & Gmail Authentication](#first-launch--gmail-authentication)
- [Using the Application](#using-the-application)
- [Features](#features)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

---

## What is This?

This is a tool that:
1. **Reads emails** from your Gmail inbox
2. **Uses AI** (Google Gemini, Claude, or OpenAI) to turn those emails into Polish news articles
3. **Gives you a web page** to manage everything — fetch emails, preview articles, edit, and download

You don't need to be technical to use it. Just follow the steps below.

---

## Requirements

Before you begin, make sure you have:

| Requirement | How to Get It |
|-------------|---------------|
| **Python 3.10 or newer** | Download from [python.org](https://www.python.org/downloads/) |
| **A Google account** | For Gmail access |
| **An AI API key** | Free from [Google AI Studio](https://aistudio.google.com/apikey) (recommended) |

> **How to check if Python is installed:**  
> Open Terminal (Mac/Linux) or Command Prompt (Windows) and type:  
> ```
> python3 --version
> ```  
> If you see something like `Python 3.11.4`, you're good. If you get an error, install Python from the link above.

---

## Download

### Option A: Download as ZIP (Easiest)

1. Go to the project page on GitHub
2. Click the green **Code** button
3. Click **Download ZIP**
4. Find the downloaded file (usually in your Downloads folder)
5. Right-click the file → **Extract All** (Windows) or **Double-click** (Mac/Linux)
6. Open the extracted folder

### Option B: Clone with Git (Advanced)

If you have Git installed, open Terminal/Command Prompt and run:

```bash
git clone https://github.com/your-repo/pruszkow-news-pipeline.git
cd pruszkow-news-pipeline
```

---

## First-Time Setup

### Windows Setup

#### Step 1: Open the project folder
- Find where you extracted/downloaded the folder
- Open it

#### Step 2: Run the starter script
- Double-click the file called **`start.bat`**
- A black window will appear — this is normal

#### Step 3: Follow the on-screen instructions
The script will:
1. Check if Python is installed ✓
2. Create a settings file (`.env`) ✓
3. Ask you to choose an AI provider (type `1` for Gemini — it's free) ✓
4. Ask for your API key (paste it in) ✓
5. Ask what port to use (just press Enter for default) ✓
6. Install everything needed automatically ✓
7. Start the server ✓

#### Step 4: Open your browser
- Go to: **http://localhost:8000**
- You'll see the application!

---

### macOS Setup

#### Step 1: Open Terminal
- Press `Cmd + Space` to open Spotlight
- Type `Terminal` and press Enter

#### Step 2: Navigate to the project folder
```bash
cd /path/to/pruszkow-news-pipeline
```
(Replace `/path/to/` with where you downloaded it. You can also type `cd ` then drag the folder into the Terminal window.)

#### Step 3: Make the starter script executable (first time only)
```bash
chmod +x start.sh
```

#### Step 4: Run the starter script
```bash
./start.sh
```

#### Step 5: Follow the on-screen instructions
The script will:
1. Check if Python 3 is installed ✓
2. Create a settings file (`.env`) ✓
3. Ask you to choose an AI provider (type `1` for Gemini — it's free) ✓
4. Ask for your API key (paste it in) ✓
5. Ask what port to use (just press Enter for default) ✓
6. Install everything needed automatically ✓
7. Start the server ✓

#### Step 6: Open your browser
- Go to: **http://localhost:8000**
- You'll see the application!

---

### Linux Setup

#### Step 1: Open Terminal
- Press `Ctrl + Alt + T` (on most distributions)
- Or search for "Terminal" in your applications

#### Step 2: Navigate to the project folder
```bash
cd /path/to/pruszkow-news-pipeline
```

#### Step 3: Make the starter script executable (first time only)
```bash
chmod +x start.sh
```

#### Step 4: Run the starter script
```bash
./start.sh
```

#### Step 5: Follow the on-screen instructions
The script will:
1. Check if Python 3 is installed ✓
2. Create a settings file (`.env`) ✓
3. Ask you to choose an AI provider (type `1` for Gemini — it's free) ✓
4. Ask for your API key (paste it in) ✓
5. Ask what port to use (just press Enter for default) ✓
6. Install everything needed automatically ✓
7. Start the server ✓

#### Step 6: Open your browser
- Go to: **http://localhost:8000**
- You'll see the application!

---

## Starter Scripts Explained

### What does `start.sh` do? (Mac & Linux)

| Step | What Happens |
|------|--------------|
| 1 | Checks if Python 3 is installed |
| 2 | Creates `.env` file from `.env.example` if it doesn't exist |
| 3 | Asks you to choose an AI provider (Gemini, Claude, or OpenAI) |
| 4 | Asks for your API key and saves it |
| 5 | Checks if Gmail credentials (`client_secret.json`) exist |
| 6 | Creates data folders (`data/articles`, `data/attachments`) |
| 7 | Creates a virtual environment (isolated Python space) |
| 8 | Installs all required packages |
| 9 | Asks what port to use (default: 8000) |
| 10 | Starts the server |

### What does `start.bat` do? (Windows)

Same as above, but for Windows. It uses PowerShell to update settings files.

### What is a virtual environment?

A virtual environment is a isolated space for Python packages. It keeps this project's packages separate from your other Python projects. The script creates it automatically — you don't need to do anything.

---

## First Launch & Gmail Authentication

After starting the server for the first time:

### Step 1: Open the application
- Go to **http://localhost:8000** in your browser

### Step 2: Connect your Gmail
1. Click the **Settings** tab at the top
2. Click **Connect Gmail**
3. A new window will open asking you to sign in to Google
4. Sign in with the Gmail account you want to use
5. Allow the permissions (this lets the app read your emails)
6. You'll be redirected back to the application

### Step 3: Start using it!
- Go to the **Email Manager** tab to fetch emails
- Go to the **Article Generator** tab to create articles
- Go to the **Dashboard** to see an overview

> **Note:** You only need to do the Gmail authentication once. The app remembers your login.

---

## Using the Application

### Basic Workflow

1. **Fetch Emails**
   - Go to "Email Manager"
   - Click "Fetch Emails"
   - Select which emails you want to turn into articles

2. **Generate Articles**
   - Go to "Article Generator"
   - Select the emails you want to process
   - Click "Generate Article"
   - The AI will create a Polish news article

3. **Review & Edit**
   - Go to "Article Viewer"
   - Read the generated article
   - Edit if needed
   - Download when ready

---

## Features

- **Dashboard** - Overview of emails and articles
- **Email Manager** - Fetch, preview, and select emails from Gmail
- **Article Generator** - AI-powered Polish news articles
- **Article Viewer** - Read, edit, and download articles
- **Settings** - Configure API keys and preferences
- **Multiple AI Providers** - Choose between Gemini, Claude, or OpenAI

---

## Project Structure

```
pruszkow-news-pipeline/
├── backend/                    # Server code
│   ├── main.py                 # Main application
│   ├── config.py               # Settings
│   ├── models.py               # Data models
│   ├── services/               # Business logic
│   │   ├── gmail.py           # Gmail integration
│   │   ├── gemini.py          # AI generation
│   │   └── database.py        # Data storage
│   └── routes/                 # API endpoints
│       ├── emails.py           # Email handling
│       ├── articles.py         # Article handling
│       └── settings.py         # Configuration
├── frontend/                   # Web interface
│   ├── index.html              # Main page
│   ├── css/style.css           # Styles
│   └── js/
│       ├── api.js              # Server communication
│       └── app.js              # Application logic
├── data/                       # Generated data (created on first run)
├── requirements.txt            # Python packages needed
├── .env.example               # Settings template
├── start.sh                   # Mac/Linux starter script
└── start.bat                  # Windows starter script
```

---

## Troubleshooting

### "Python not found" error
- Install Python from [python.org](https://www.python.org/downloads/)
- **Important:** During installation, check the box that says "Add Python to PATH"

### "Port already in use" error
- Another program is using port 8000
- When the script asks for a port, type a different number (e.g., `8001`)
- Then go to `http://localhost:8001` instead

### Gmail won't connect
- Make sure you have `client_secret.json` in the project folder
- Download it from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- Make sure Gmail API is enabled in your Google Cloud project

### Application starts but shows errors
- Check that your API key is correct in the `.env` file
- Make sure you copied the full key without extra spaces

---

## Security

- **Never share** your `client_secret.json`, `token.json`, or `.env` files
- These files are already in `.gitignore` so they won't be uploaded to GitHub
- To revoke access: Go to [Google Account Permissions](https://myaccount.google.com/permissions)
- Your API keys are stored locally and never sent anywhere except the AI provider you choose

---

## Need Help?

If you run into issues:
1. Check the [Troubleshooting](#troubleshooting) section above
2. Make sure you followed all steps in order
3. Try deleting the `venv` folder and running the starter script again
