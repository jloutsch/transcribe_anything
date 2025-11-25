# Audio/Video Transcription App

Local, privacy-focused audio and video transcription using OpenAI's Whisper model (via Faster Whisper). No cloud services required - everything runs on your Mac.

## Features

- 🎙️ **Two interfaces**: Command-line and GUI
- 🔒 **100% local processing** - No data sent to cloud services
- 📁 **Drag and drop support** in GUI version
- 🎬 **Multiple formats**: MP4, MOV, MP3, WAV, M4A, FLAC, OGG, and more
- ⚡ **Fast transcription** using optimized Whisper models
- 📝 **Timestamped output** for easy reference
- 🌍 **Auto language detection**

## Quick Start

### Automated Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/jloutsch/transcription-app.git
cd transcription-app

# Run the installer
./install.sh
```

The installer will:
- Check for and install Python 3.13 if needed (via Homebrew)
- Install required system packages (tkinter, ffmpeg)
- Create a virtual environment
- Install all Python dependencies
- Configure the launcher script

After installation, run the app with:
```bash
./launch_gui.sh
```

### Manual Installation

**Prerequisites:**
- Python 3.13 (recommended) or Python 3.11+
- Homebrew (for macOS dependencies)

```bash
# Clone the repository
git clone https://github.com/jloutsch/transcription-app.git
cd transcription-app

# Install system dependencies
brew install python@3.13 python-tk@3.13

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

## Usage

### Option 1: GUI Application (Recommended)

Run the graphical interface with drag-and-drop support:

```bash
python transcribe_gui.py
```

**Features:**
- Drag and drop audio/video files
- Choose output folder
- Visual progress indication
- Add multiple files to queue
- Processes one file at a time

**Steps:**
1. Click "Choose" to select output folder
2. Drag files into the drop zone (or click "Add Files")
3. Click "Start Transcription"
4. Transcripts saved as `.txt` files with timestamps

### Option 2: Command Line

Batch process all media files in a directory:

```bash
python transcribe_videos.py
```

The script will:
- Find all audio/video files in current directory
- Show you what it found
- Ask for confirmation
- Transcribe each file
- Save transcripts to `transcripts/` folder

## Supported Formats

### Video
`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`

### Audio
`.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.aac`, `.wma`, `.opus`

## Output Format

Transcripts are saved as text files with timestamps and metadata:

```
Transcript: example.mp4
Language: en
Duration: 125.50 seconds
--------------------------------------------------------------------------------

[00:00:00 --> 00:00:05]
Hello and welcome to this training session.

[00:00:05 --> 00:00:12]
Today we're going to discuss networking strategies.
```

## Configuration

Edit the model size in either script for different speed/accuracy tradeoffs:

```python
MODEL_SIZE = "medium"  # Options: tiny, base, small, medium, large-v3
```

**Model Comparison:**
- `tiny` - Fastest, least accurate (~1GB RAM)
- `base` - Fast, basic accuracy (~1GB RAM)
- `small` - Balanced (~2GB RAM)
- `medium` - Good accuracy (default, ~5GB RAM)
- `large-v3` - Best accuracy, slower (~10GB RAM)

## Creating a Mac .app Bundle (Optional)

After running `install.sh`, you can create a double-clickable Mac application:

### Using Platypus (Recommended)

1. Download and install [Platypus](https://sveinbjorn.org/platypus)
2. Open Platypus
3. Configure:
   - **Script Type:** Shell
   - **Script Path:** Browse to `/path/to/transcription-app/launch_gui.sh`
   - **Interface:** None
   - **Options:** Check "Runs in background"
4. Click "Create App"
5. Save as "Transcribe Anything.app"

The created .app will work **only on your machine** since it contains absolute paths. For sharing with others, distribute the repository and have them run `install.sh` on their machine.

### Distribution Best Practices

When sharing this app:
1. Share the GitHub repository link
2. Users clone the repo and run `./install.sh`
3. (Optional) Users create their own .app with Platypus using their `launch_gui.sh`

This approach ensures:
- All dependencies are correctly installed for each system
- Paths are configured correctly for each machine
- Model downloads happen on first use (not bundled in repo)

## Performance Tips

- **First run**: Model will be downloaded (~500MB-1.5GB depending on size)
- **Processing time**: ~1x speed on modern hardware (10 min audio = ~10 min processing)
- **Memory**: Ensure enough RAM for selected model size
- **GPU**: Automatically uses GPU if available (CUDA on compatible hardware)

## Troubleshooting

### "Command not found: ffmpeg"
```bash
brew install ffmpeg
```

### Drag-and-drop not working in GUI
```bash
pip install tkinterdnd2
```
If still not working, use the "Add Files" button.

### macOS security warning
Go to System Preferences → Security & Privacy → Click "Open Anyway"

Or run:
```bash
xattr -dr com.apple.quarantine /path/to/app
```

## Privacy

- All processing happens locally on your machine
- No internet connection required (after initial model download)
- No data sent to external services
- Audio/video files never leave your computer

## Dependencies

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Optimized Whisper implementation
- [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2) - Drag-and-drop support
- [tqdm](https://github.com/tqdm/tqdm) - Progress bars
- [FFmpeg](https://ffmpeg.org/) - Audio/video processing

## License

MIT License - feel free to use and modify!

## Contributing

Issues and pull requests welcome!

## Credits

Built with OpenAI's Whisper model and the excellent Faster Whisper implementation.
