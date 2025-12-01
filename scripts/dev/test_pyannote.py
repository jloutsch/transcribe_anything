#!/usr/bin/env python3
"""
Test pyannote.audio speaker diarization with Whisper transcription.

This script tests the accuracy of pyannote for speaker diarization
and aligns the results with Whisper word-level timestamps.

Requirements:
    pip install pyannote.audio faster-whisper torch torchaudio

Usage:
    python test_pyannote.py <audio_file> [--token YOUR_HF_TOKEN] [--num-speakers 2]

You need a HuggingFace token with access to:
    - pyannote/speaker-diarization-3.1
    - pyannote/segmentation-3.0
"""

import sys
import os
import argparse
from pathlib import Path

# Check for required packages
try:
    from pyannote.audio import Pipeline
    HAS_PYANNOTE = True
except ImportError:
    HAS_PYANNOTE = False
    print("ERROR: pyannote.audio not installed. Run: pip install pyannote.audio")

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False
    print("ERROR: faster-whisper not installed. Run: pip install faster-whisper")


def get_hf_token(token_arg: str = None) -> str:
    """Get HuggingFace token from argument, environment, or prompt."""
    # Try argument first
    if token_arg:
        return token_arg

    # Try local .hf_token file (project-specific)
    local_token_path = Path(__file__).parent / ".hf_token"
    if local_token_path.exists():
        token = local_token_path.read_text().strip()
        if token:
            return token

    # Try environment variable
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if token:
        return token

    # Try HuggingFace CLI cache
    hf_token_path = Path.home() / ".cache" / "huggingface" / "token"
    if hf_token_path.exists():
        return hf_token_path.read_text().strip()
    
    # Prompt user
    print("\n" + "="*60)
    print("HuggingFace Token Required")
    print("="*60)
    print("To use pyannote speaker diarization, you need a HuggingFace token.")
    print("\nSteps:")
    print("1. Create account at https://huggingface.co/join")
    print("2. Accept terms at https://huggingface.co/pyannote/speaker-diarization-3.1")
    print("3. Accept terms at https://huggingface.co/pyannote/segmentation-3.0")
    print("4. Get token at https://huggingface.co/settings/tokens")
    print("\nYou can also set HF_TOKEN environment variable.")
    print("="*60 + "\n")
    
    token = input("Enter your HuggingFace token: ").strip()
    if not token:
        print("No token provided. Exiting.")
        sys.exit(1)
    
    return token


def transcribe_with_whisper(audio_path: str, model_size: str = "medium"):
    """Transcribe audio using Whisper with word timestamps."""
    print(f"\n[1/4] Loading Whisper {model_size} model...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    print(f"[2/4] Transcribing audio...")
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=100)
    )
    
    # Collect all words with timestamps
    all_words = []
    segments_list = []
    for segment in segments:
        segments_list.append(segment)
        if hasattr(segment, 'words') and segment.words:
            for word in segment.words:
                all_words.append({
                    'word': word.word.strip(),
                    'start': word.start,
                    'end': word.end
                })
    
    print(f"    Detected language: {info.language}")
    print(f"    Duration: {info.duration:.1f} seconds")
    print(f"    Words extracted: {len(all_words)}")
    
    return all_words, segments_list, info


def diarize_with_pyannote(audio_path: str, hf_token: str, num_speakers: int = None):
    """Run pyannote speaker diarization."""
    print(f"\n[3/4] Loading pyannote diarization pipeline...")
    
    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token
        )
    except Exception as e:
        print(f"\nERROR loading pyannote pipeline: {e}")
        print("\nMake sure you have:")
        print("1. Accepted the model terms on HuggingFace")
        print("2. A valid access token")
        sys.exit(1)
    
    print(f"    Running diarization...")
    
    # Run diarization with optional speaker count
    if num_speakers:
        diarization = pipeline(audio_path, num_speakers=num_speakers)
    else:
        diarization = pipeline(audio_path)
    
    # Extract speaker segments
    # New API: diarization is a DiarizeOutput object with .segments attribute
    speaker_segments = []

    # Try new API first (diarization.segments)
    if hasattr(diarization, 'segments'):
        for segment in diarization.segments:
            speaker_segments.append({
                'start': segment.start,
                'end': segment.end,
                'speaker': segment.speaker
            })
    # Fallback to old API (iter tracks)
    elif hasattr(diarization, 'itertracks'):
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speaker_segments.append({
                'start': turn.start,
                'end': turn.end,
                'speaker': speaker
            })
    else:
        # Try iterating directly
        for item in diarization:
            speaker_segments.append({
                'start': item.start,
                'end': item.end,
                'speaker': item.speaker
            })
    
    # Count unique speakers
    unique_speakers = set(seg['speaker'] for seg in speaker_segments)
    print(f"    Detected {len(unique_speakers)} speakers")
    print(f"    Total segments: {len(speaker_segments)}")
    
    return speaker_segments


def assign_speakers_to_words(words: list, speaker_segments: list) -> list:
    """Assign speaker labels to each word based on timestamps."""
    print(f"\n[4/4] Aligning speakers to words...")
    
    for word in words:
        word_center = (word['start'] + word['end']) / 2
        
        # Find the speaker segment that contains this word's center
        word['speaker'] = 'UNKNOWN'
        for seg in speaker_segments:
            if seg['start'] <= word_center <= seg['end']:
                word['speaker'] = seg['speaker']
                break
    
    # Count assignments
    assigned = sum(1 for w in words if w['speaker'] != 'UNKNOWN')
    print(f"    Words assigned: {assigned}/{len(words)}")
    
    return words


def format_transcript(words: list) -> str:
    """Format words into a readable transcript grouped by speaker."""
    if not words:
        return "No words transcribed."
    
    lines = []
    current_speaker = None
    current_text = []
    
    for word in words:
        speaker = word['speaker']
        if speaker != current_speaker:
            # Output previous speaker's text
            if current_text:
                lines.append(f"{current_speaker}: {' '.join(current_text)}\n")
            current_speaker = speaker
            current_text = [word['word']]
        else:
            current_text.append(word['word'])
    
    # Output final speaker's text
    if current_text:
        lines.append(f"{current_speaker}: {' '.join(current_text)}\n")
    
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Test pyannote speaker diarization with Whisper transcription'
    )
    parser.add_argument('audio_file', help='Path to audio file')
    parser.add_argument('--token', help='HuggingFace access token')
    parser.add_argument('--num-speakers', type=int, help='Number of speakers (optional)')
    parser.add_argument('--model', default='medium', help='Whisper model size (default: medium)')
    parser.add_argument('--output', help='Output file path (default: <audio_name>_diarized.txt)')
    
    args = parser.parse_args()
    
    # Validate input
    if not Path(args.audio_file).exists():
        print(f"ERROR: Audio file not found: {args.audio_file}")
        sys.exit(1)
    
    if not HAS_PYANNOTE or not HAS_WHISPER:
        sys.exit(1)
    
    # Get HuggingFace token
    hf_token = get_hf_token(args.token)
    
    print("\n" + "="*60)
    print("Pyannote Diarization Test")
    print("="*60)
    print(f"Audio: {args.audio_file}")
    print(f"Model: {args.model}")
    if args.num_speakers:
        print(f"Speakers: {args.num_speakers}")
    
    # Step 1-2: Transcribe with Whisper
    words, segments, info = transcribe_with_whisper(args.audio_file, args.model)
    
    # Step 3: Diarize with pyannote
    speaker_segments = diarize_with_pyannote(args.audio_file, hf_token, args.num_speakers)
    
    # Step 4: Align speakers to words
    words_with_speakers = assign_speakers_to_words(words, speaker_segments)
    
    # Format output
    transcript = format_transcript(words_with_speakers)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = Path(args.audio_file).stem + "_diarized.txt"
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"Transcript: {Path(args.audio_file).name}\n")
        f.write(f"Language: {info.language}\n")
        f.write(f"Duration: {info.duration:.2f} seconds\n")
        f.write(f"Speakers: {len(set(seg['speaker'] for seg in speaker_segments))}\n")
        f.write("-" * 60 + "\n\n")
        f.write(transcript)
    
    print("\n" + "="*60)
    print("Results")
    print("="*60)
    print(f"\nOutput saved to: {output_path}")
    print("\nTranscript preview:")
    print("-" * 40)
    # Show first 1000 chars
    preview = transcript[:1000]
    if len(transcript) > 1000:
        preview += "\n... (truncated)"
    print(preview)
    print("-" * 40)


if __name__ == '__main__':
    main()
