#!/bin/bash
set -e

echo "🎙️  Installing Audio Transcription App..."
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Please install from https://brew.sh"
    exit 1
fi

# Check for Python 3.13
if ! command -v python3.13 &> /dev/null; then
    echo "📦 Installing Python 3.13..."
    brew install python@3.13
fi

# Install python-tk
echo "📦 Installing Python tkinter..."
brew install python-tk@3.13 2>/dev/null || true

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create virtual environment
echo "🐍 Creating virtual environment..."
python3.13 -m venv venv

# Activate and install dependencies
echo "📚 Installing Python packages..."
source venv/bin/activate
pip install --quiet -r requirements.txt

# Update launch script with current directory
echo "🔧 Configuring launcher..."
cat > launch_gui.sh << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
source venv/bin/activate
python transcribe_gui.py
EOF

chmod +x launch_gui.sh

echo ""
echo "✅ Installation complete!"
echo ""
echo "To run the app:"
echo "  1. Double-click: launch_gui.sh"
echo "  2. Or run: ./launch_gui.sh"
echo ""
echo "Optional: Create a Mac .app with Platypus"
echo "  1. Install Platypus: https://sveinbjorn.org/platypus"
echo "  2. Script Path: $SCRIPT_DIR/launch_gui.sh"
echo "  3. Script Type: Shell"
echo "  4. Interface: None"
echo "  5. Check 'Runs in background'"
echo ""
