#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Cross-platform sed -i (macOS needs '', Linux does not)
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed_inplace() { sed -i '' "$@"; }
else
    sed_inplace() { sed -i "$@"; }
fi

echo "========================================="
echo "  Pruszkow News Pipeline - First Setup"
echo "========================================="
echo "                                    v-2.0"
# echo "========================================="
echo ""

# --- Check Python ---
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 not found. Install Python 3.10+ first."
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[OK] Python $PYTHON_VERSION"

# --- Create .env from example if missing ---
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[OK] Created .env from .env.example"
    else
        echo "[WARN] No .env.example found. Creating minimal .env..."
        cat > .env <<'EOF'
HOST=0.0.0.0
PORT=8000
GMAIL_CREDENTIALS_FILE=client_secret.json
AI_PROVIDER=gemini
GEMINI_API_KEY=
CLAUDE_API_KEY=
OPENAI_API_KEY=
EOF
        echo "[OK] Created minimal .env"
    fi
else
    echo "[OK] .env exists"
fi

# --- Interactive setup if keys are empty ---
source_env() {
    set -a
    source .env
    set +a
}
source_env

needs_setup=false
if [ -z "$GEMINI_API_KEY" ] && [ -z "$CLAUDE_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    needs_setup=true
fi

if [ "$needs_setup" = true ]; then
    echo ""
    echo "--- First-Time Setup ---"
    echo "No API keys found. Let's configure your AI provider."
    echo ""

    # Provider selection
    echo "Select AI provider:"
    echo "  1) Google Gemini (recommended, free tier available)"
    echo "  2) Anthropic Claude"
    echo "  3) OpenAI"
    echo ""
    read -p "Choice [1]: " PROVIDER_CHOICE
    PROVIDER_CHOICE=${PROVIDER_CHOICE:-1}

    case $PROVIDER_CHOICE in
        1) PROVIDER="gemini" ;;
        2) PROVIDER="claude" ;;
        3) PROVIDER="openai" ;;
        *) PROVIDER="gemini" ;;
    esac

    echo ""
    case $PROVIDER in
        gemini)
            echo "Get your key at: https://aistudio.google.com/apikey"
            read -p "Gemini API Key: " API_KEY
            sed_inplace "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=$API_KEY/" .env
            ;;
        claude)
            echo "Get your key at: https://console.anthropic.com/"
            read -p "Claude API Key: " API_KEY
            sed_inplace "s/^CLAUDE_API_KEY=.*/CLAUDE_API_KEY=$API_KEY/" .env
            ;;
        openai)
            echo "Get your key at: https://platform.openai.com/api-keys"
            read -p "OpenAI API Key: " API_KEY
            sed_inplace "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=$API_KEY/" .env
            ;;
    esac

    sed_inplace "s/^AI_PROVIDER=.*/AI_PROVIDER=$PROVIDER/" .env
    source_env
    echo "[OK] API key configured for $PROVIDER"
else
    echo "[OK] API keys found (provider: $AI_PROVIDER)"
fi

# --- Check Gmail credentials ---
if [ -f "$GMAIL_CREDENTIALS_FILE" ]; then
    echo "[OK] Gmail credentials: $GMAIL_CREDENTIALS_FILE"
else
    echo "[WARN] Gmail credentials not found: $GMAIL_CREDENTIALS_FILE"
    echo "       Download from: https://console.cloud.google.com/apis/credentials"
    echo "       Place the JSON file in the project root."
fi

# --- Check Gmail token ---
if [ -f "token.json" ]; then
    echo "[OK] Gmail token found (authenticated)"
else
    echo "[INFO] Gmail not yet authenticated. Connect via the Settings page after startup."
fi

# --- Create data directories ---
mkdir -p data/articles data/attachments
echo "[OK] Data directories ready"

# --- Create virtual environment ---
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "[OK] Virtual environment created"
else
    echo "[OK] Virtual environment exists"
fi

# --- Activate venv ---
source venv/bin/activate

# --- Install dependencies ---
echo "Checking dependencies..."
pip install -q -r requirements.txt
echo "[OK] Dependencies installed"

# --- Ask for port ---
echo ""
read -p "Enter port number (default ${PORT:-8000}): " INPUT_PORT
PORT=${INPUT_PORT:-${PORT:-8000}}

if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] Port must be a number."
    exit 1
fi

# --- Update port in .env ---
sed_inplace "s/^PORT=.*/PORT=$PORT/" .env

echo ""
echo "========================================="
echo "  Server starting at http://localhost:$PORT"
echo "  Press Ctrl+C to stop"
echo "========================================="
echo ""

uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" --reload
