#!/usr/bin/env python3
"""
Test WavLM speaker diarization on an audio file
"""
import sys
import torchaudio
import torch
import numpy as np
from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
from sklearn.cluster import AgglomerativeClustering
from faster_whisper import WhisperModel

def test_wavlm_diarization(audio_path, num_speakers=2):
    print(f"Testing WavLM diarization on: {audio_path}")

    # Load WavLM models
    print("Loading WavLM models...")
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained('microsoft/wavlm-base-plus-sv')
    wavlm_model = WavLMForXVector.from_pretrained('microsoft/wavlm-base-plus-sv')
    print("WavLM models loaded!")

    # Load Whisper for transcription
    print("Loading Whisper model...")
    whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
    print("Whisper loaded!")

    # Transcribe with word timestamps
    print("Transcribing audio...")
    segments, info = whisper_model.transcribe(audio_path, word_timestamps=True)
    segments_list = list(segments)
    print(f"Got {len(segments_list)} segments")

    # Collect all words
    all_words = []
    for segment in segments_list:
        if hasattr(segment, 'words') and segment.words:
            all_words.extend(segment.words)

    print(f"Got {len(all_words)} words with timestamps")

    # Load audio
    waveform, sample_rate = torchaudio.load(audio_path)

    # Resample if needed
    if sample_rate != 16000:
        print(f"Resampling from {sample_rate}Hz to 16000Hz...")
        resampler = torchaudio.transforms.Resample(sample_rate, 16000)
        waveform = resampler(waveform)
        sample_rate = 16000

    # Extract embeddings for each word
    print(f"Extracting embeddings for {len(all_words)} words...")
    embeddings_list = []

    for i, word in enumerate(all_words):
        if i % 10 == 0:
            print(f"  Progress: {i}/{len(all_words)}")

        try:
            start_sample = int(word.start * sample_rate)
            end_sample = int(word.end * sample_rate)
            word_audio = waveform[:, start_sample:end_sample]

            # Extract embedding
            inputs = feature_extractor(word_audio.squeeze().numpy(), sampling_rate=16000, return_tensors="pt", padding=True)
            with torch.no_grad():
                embedding = wavlm_model(**inputs).embeddings
                embedding = torch.nn.functional.normalize(embedding, dim=-1)
            embeddings_list.append(embedding[0].cpu().numpy())
        except Exception as e:
            print(f"Failed to extract embedding for word at {word.start:.2f}s: {e}")
            embeddings_list.append(np.zeros(512))

    # Cluster embeddings
    embeddings_array = np.array(embeddings_list)
    print(f"Clustering {len(embeddings_array)} embeddings into {num_speakers} speakers...")

    clustering = AgglomerativeClustering(n_clusters=num_speakers, metric='cosine', linkage='average')
    speaker_ids = clustering.fit_predict(embeddings_array)

    unique_speakers = len(set(speaker_ids))
    print(f"Found {unique_speakers} distinct speakers")

    # Assign speakers to words
    for i, word in enumerate(all_words):
        word.speaker = f"SPEAKER_{speaker_ids[i]:02d}"

    # Print results
    print("\n=== Diarization Results ===")
    current_speaker = None
    current_text = []

    for word in all_words:
        if word.speaker != current_speaker:
            if current_text:
                print(f"\n{current_speaker}: {' '.join(current_text)}")
            current_speaker = word.speaker
            current_text = [word.word.strip()]
        else:
            current_text.append(word.word.strip())

    # Print last segment
    if current_text:
        print(f"\n{current_speaker}: {' '.join(current_text)}")

    print(f"\n=== Done! ===")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_wavlm.py <audio_file> [num_speakers]")
        sys.exit(1)

    audio_path = sys.argv[1]
    num_speakers = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    test_wavlm_diarization(audio_path, num_speakers)
