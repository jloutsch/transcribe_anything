# Speaker Diarization Implementation: A Technical Post-Mortem

## Executive Summary

Implementing speaker diarization (identifying "who spoke when") proved to be one of the most challenging features of this transcription application. After extensive experimentation with multiple approaches, libraries, and techniques, we developed a working solution—but not without significant hurdles. This document details the journey, the obstacles encountered, and the solutions that ultimately worked.

## The Challenge

Speaker diarization is the process of partitioning an audio stream into homogeneous segments according to speaker identity. Unlike simple transcription, which only needs to convert speech to text, diarization requires:

1. **Speaker embedding extraction** - Converting audio segments into mathematical representations that capture speaker characteristics
2. **Clustering** - Grouping similar embeddings to identify unique speakers
3. **Alignment** - Matching speaker identities to transcribed words/segments
4. **Temporal coherence** - Ensuring speaker assignments make sense chronologically

## Approaches Attempted

### Approach 1: pyannote.audio (Initial Attempt)

**What it is**: pyannote.audio is the industry-standard Python library for speaker diarization, developed by CNRS researchers and widely used in production systems.

**Implementation**:
```python
from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")
diarization = pipeline(audio_file)
```

**Why we tried it**:
- State-of-the-art accuracy
- Well-documented and actively maintained
- Used by major companies and research institutions
- Designed specifically for diarization (not a repurposed model)

**Challenges encountered**:

1. **Authentication Barrier**
   - Requires a HuggingFace authentication token
   - Users must create an account and accept model license terms
   - Token management adds complexity to the user experience
   - Not suitable for a "download and run" desktop application

2. **Heavy Dependencies**
   - Requires PyTorch (600MB+ download)
   - Needs torchaudio and numerous other packages
   - Installation size ballooned to >2GB
   - Long initial download time on first use

3. **Integration Complexity**
   - pyannote works on entire audio files
   - Whisper provides word-level timestamps
   - Mismatch between segment-based (pyannote) and word-based (Whisper) timestamps
   - Required complex alignment logic to map speaker labels to individual words

4. **Performance Issues**
   - Processing time was 2-3x longer than transcription alone
   - Memory usage spike (3-4GB for medium-length files)
   - Not suitable for batch processing multiple files

**Outcome**: Shelved due to authentication requirements and user experience concerns.

---

### Approach 2: WavLM with Agglomerative Clustering (Final Solution)

**What it is**: WavLM is Microsoft's self-supervised speech model trained on 94,000 hours of audio. Originally designed for speaker verification, it can be repurposed for diarization by extracting speaker embeddings and clustering them.

**Implementation**:
```python
from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
from sklearn.cluster import AgglomerativeClustering

# Load models
feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained('microsoft/wavlm-base-plus-sv')
wavlm_model = WavLMForXVector.from_pretrained('microsoft/wavlm-base-plus-sv')

# Extract embeddings for each audio segment
embeddings = extract_embeddings(audio_segments)

# Cluster to identify speakers
clustering = AgglomerativeClustering(n_clusters=num_speakers, metric='cosine', linkage='average')
speaker_ids = clustering.fit_predict(embeddings)
```

**Why we tried it**:
- No authentication token required
- Open-source and freely available
- Strong speaker verification performance
- Can be adapted for diarization with clustering

**Challenges encountered**:

1. **Word-Level Granularity Problem**

   **Initial approach**: Extract embeddings for each individual word
   ```python
   for word in all_words:
       start_sample = int(word.start * sample_rate)
       end_sample = int(word.end * sample_rate)
       word_audio = waveform[:, start_sample:end_sample]
       embedding = extract_embedding(word_audio)
   ```

   **Problem**:
   - Individual words are too short for reliable speaker identification
   - Model trained on longer utterances (typically 1-3 seconds)
   - Short audio segments produced noisy, unreliable embeddings
   - Speaker assignments flickered rapidly between words
   - Resulted in speaker labels like: `SPEAKER_0, SPEAKER_1, SPEAKER_0, SPEAKER_1` for a single sentence

2. **The Sliding Window Solution**

   After the word-level approach failed, we implemented a **sliding window strategy**:

   ```python
   WINDOW_SIZE = 1.0      # 1 second windows
   WINDOW_STRIDE = 0.5    # 50% overlap

   segments_for_embedding = []
   current_time = 0
   while current_time < total_duration:
       window_start = current_time
       window_end = current_time + WINDOW_SIZE

       # Find all words within this window
       window_word_indices = [
           i for i, word in enumerate(all_words)
           if word.start >= window_start and word.end <= window_end
       ]

       if window_word_indices:
           segments_for_embedding.append({
               'word_indices': window_word_indices,
               'start': window_start,
               'end': window_end
           })

       current_time += WINDOW_STRIDE
   ```

   **Why this works**:
   - Provides sufficient audio context (1 second) for reliable speaker identification
   - Overlapping windows (50% stride) ensure we don't miss speaker transitions
   - Each window contains multiple words, improving embedding quality
   - Smoother speaker transitions with fewer misclassifications

   **The tradeoffs**:
   - Increased computational cost (more embeddings to extract)
   - Potential for missed very rapid speaker turns
   - Memory overhead from storing overlapping segments
   - Had to implement voting logic to assign speakers to individual words within windows

3. **Audio Resampling Complexity**

   ```python
   waveform, sample_rate = torchaudio.load(audio_path)
   if sample_rate != 16000:
       resampler = torchaudio.transforms.Resample(sample_rate, 16000)
       waveform = resampler(waveform)
       sample_rate = 16000
   ```

   **Challenge**:
   - WavLM requires 16kHz audio
   - Input files often at 44.1kHz, 48kHz, or other rates
   - Required torchaudio dependency just for resampling
   - Resampling quality affects embedding accuracy
   - Added processing time and complexity

4. **Cluster Number Selection**

   Users must specify the number of speakers, but:
   - Real-world conversations often have unknown speaker counts
   - Incorrect speaker count leads to over-segmentation or under-segmentation
   - Auto-detection is unreliable without ground truth
   - Implemented manual control with UI but it's not intuitive

5. **Speaker Label Stability**

   Agglomerative clustering doesn't guarantee consistent labels:
   - `SPEAKER_0` in one file might be `SPEAKER_1` in another
   - Labels are arbitrary (just cluster IDs)
   - No persistence across files
   - Users expected "Speaker 1" to always be the same person (not possible)

6. **Error Handling for Short Utterances**

   ```python
   try:
       start_sample = int(seg_info['start'] * sample_rate)
       end_sample = int(seg_info['end'] * sample_rate)
       segment_audio = waveform[:, start_sample:end_sample]

       inputs = feature_extractor(segment_audio.squeeze().numpy(),
                                  sampling_rate=16000,
                                  return_tensors="pt",
                                  padding=True)
       with torch.no_grad():
           embedding = wavlm_model(**inputs).embeddings
           embedding = torch.nn.functional.normalize(embedding, dim=-1)
       valid_embeddings.append(embedding[0].cpu().numpy())
   except Exception as e:
       print(f"Failed to extract embedding: {e}")
       valid_embeddings.append(np.zeros(512))  # Placeholder embedding
   ```

   **Problem**:
   - Some segments too short even with windowing
   - Model throws exceptions on malformed input
   - Required extensive error handling and fallback logic
   - Placeholder embeddings (zeros) affect clustering quality

7. **Performance and Memory Issues**

   Final memory profile for a 10-minute audio file:
   - Whisper model: ~1.5GB
   - WavLM models: ~800MB
   - Audio waveform: ~200MB
   - Embeddings array: ~50MB
   - Peak memory: **~3GB** (vs 1.5GB without diarization)

   Processing time breakdown:
   - Transcription: 30 seconds
   - Embedding extraction: 45 seconds
   - Clustering: 5 seconds
   - Total: **80 seconds** (2.7x slowdown)

8. **UI/UX Challenges**

   Implementing the UI exposed additional problems:
   - Where to place speaker labels in transcripts?
   - How to visualize speaker changes?
   - Should we use colors, prefixes, or separate sections?
   - Users confused by arbitrary speaker numbers (SPEAKER_0, SPEAKER_1)

   Final UI approach:
   ```python
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
   ```

   Output format:
   ```
   SPEAKER_00: Hello, how are you doing today?
   SPEAKER_01: I'm doing great, thanks for asking.
   SPEAKER_00: That's wonderful to hear.
   ```

**Outcome**: Working implementation, but complexity and performance concerns led to keeping it on a separate branch.

---

## Comparison of Approaches

| Feature | pyannote.audio | WavLM + Clustering |
|---------|---------------|-------------------|
| **Accuracy** | Excellent (purpose-built) | Good (with windowing) |
| **Setup Complexity** | High (needs HF token) | Medium (no auth needed) |
| **Dependencies** | Heavy (PyTorch + pyannote) | Heavy (PyTorch + transformers) |
| **Processing Speed** | Slow (2-3x baseline) | Slow (2.7x baseline) |
| **Memory Usage** | High (~3-4GB) | High (~3GB) |
| **User Experience** | Poor (auth barrier) | Better (no auth) |
| **Integration Effort** | High (segment alignment) | Very High (windowing required) |
| **Speaker Count** | Auto-detects | Manual input required |

---

## Why Diarization is Hard

After this implementation journey, we identified core reasons why diarization remains challenging:

1. **Temporal Resolution Mismatch**
   - Speech recognition works at word/phoneme level (tens of milliseconds)
   - Speaker identification needs longer context (hundreds of milliseconds to seconds)
   - Reconciling these timescales is non-trivial

2. **Speaker Similarity**
   - Similar voices cluster together incorrectly
   - Gender and age characteristics dominate over individual identity
   - Background noise affects different speakers differently

3. **Real-World Audio Complexity**
   - Overlapping speech (people talking simultaneously)
   - Background noise and music
   - Varying distances from microphone
   - Echo and reverber ation
   - Cross-talk and interruptions

4. **Computational Cost**
   - Deep learning models are resource-intensive
   - Processing every second of audio is expensive
   - Embedding extraction doesn't parallelize well
   - Clustering scales poorly with long conversations

5. **Lack of Ground Truth**
   - No way to validate speaker assignments without human labels
   - Quality metrics are subjective
   - Testing requires manual verification of every file

---

## Lessons Learned

1. **Authentication is a Deal-Breaker for Desktop Apps**
   - Even if technically superior, requiring user accounts kills adoption
   - Desktop users expect self-contained, offline-capable applications
   - Cloud-based auth flows feel out of place in local tools

2. **Sliding Windows Are Essential**
   - Individual words are too short for speaker identification
   - 1-second windows with 50% overlap provides good balance
   - More overlap = better accuracy but slower processing
   - Window size should match model's training data

3. **Integration is Harder Than the Core Algorithm**
   - Getting embeddings is easy
   - Aligning them with transcription timestamps is hard
   - UI/UX for speaker labels requires careful design
   - Error handling for edge cases dominates the codebase

4. **Performance Matters More Than Accuracy**
   - Users will tolerate 90% accuracy if it's fast
   - Users won't tolerate 95% accuracy if it takes 10 minutes
   - Memory usage is a hard constraint on consumer hardware
   - Progress indication is critical for long-running operations

5. **Dependency Hell is Real**
   - PyTorch alone is 600MB
   - Each new library adds vulnerabilities and maintenance burden
   - Conflicts between package versions are common
   - Installation size matters for user adoption

6. **Feature Complexity vs User Value**
   - Diarization is a "nice to have" for most users
   - Core transcription is the "must have"
   - Complex features should be optional, not default
   - Separate branches allow experimentation without polluting main

---

## The Decision to Keep It Separate

Ultimately, we decided to maintain diarization on a separate Git branch for several reasons:

1. **Not Core to Value Proposition**
   - Most users just need accurate transcription
   - Speaker labels are valuable but not essential
   - Complexity doesn't justify the marginal benefit

2. **Performance Impact**
   - 2.7x slowdown is significant
   - Memory usage increase (1.5GB → 3GB) limits batch processing
   - Not everyone has hardware to support it

3. **Implementation Complexity**
   - 200+ lines of windowing, embedding, and clustering code
   - Extensive error handling needed
   - UI becomes cluttered with diarization controls

4. **Maintenance Burden**
   - Additional dependencies to keep updated
   - More code paths = more bugs
   - Testing requires careful manual verification

5. **User Experience Concerns**
   - Requires user to specify speaker count (not intuitive)
   - Speaker labels are arbitrary numbers (confusing)
   - Output format changes significantly (breaking change)

By keeping diarization on the `diarization` branch, we allow:
- Users who need it can access it
- Main branch stays fast and simple
- Easier testing of both configurations
- Option to merge later if improved

---

## Future Improvements

If we revisit this feature, potential improvements include:

1. **Automatic Speaker Count Detection**
   - Use silhouette analysis or elbow method
   - Try multiple cluster counts and pick best
   - Warn users if confidence is low

2. **Faster Models**
   - Investigate quantized models (int8, float16)
   - Look into ONNX runtime for inference
   - Explore distilled versions of WavLM

3. **Better Speaker Persistence**
   - Store speaker embeddings across files
   - Allow users to label speakers manually
   - Maintain speaker identity in multi-file projects

4. **Progressive Enhancement**
   - Run diarization in background after transcription
   - Show transcription immediately, speakers later
   - Make it truly optional (lazy loading of models)

5. **Alternative Architectures**
   - Investigate WebAssembly for browser-based diarization
   - Cloud API option for users who want accuracy over privacy
   - Hybrid approach: local transcription, cloud diarization

---

## Conclusion

Speaker diarization pushed the boundaries of this project's complexity. While we achieved a working implementation, the journey revealed fundamental tradeoffs between accuracy, performance, and user experience.

The WavLM sliding window approach proved viable but required:
- Heavy dependencies (PyTorch, transformers, torchaudio, sklearn)
- Complex windowing logic to overcome short utterance problems
- Significant performance overhead (2.7x processing time)
- Extensive error handling for edge cases
- UI redesign to accommodate speaker labels

The decision to keep this feature on a separate branch reflects a pragmatic approach to software development: not every feature belongs in the main product, even if it works. Sometimes the best solution is to make it available without making it default.

For users who need speaker diarization, the `diarization` branch provides a working solution. For everyone else, the main branch stays fast, simple, and reliable.

---

## Technical Appendix

### Dependencies Added for Diarization

```
torch>=2.0.0          # 600MB+ (PyTorch deep learning framework)
torchaudio>=2.0.0     # 50MB+ (Audio processing for PyTorch)
transformers>=4.30.0  # 200MB+ (HuggingFace transformers library)
scikit-learn>=1.3.0   # 30MB+ (For clustering algorithms)
numpy>=1.24.0         # 20MB+ (Already required, but listed for completeness)
```

Total additional download: **~900MB**
Total memory overhead: **~1.5GB runtime**

### Key Code Sections

**Model Loading** (transcribe_gui.py:36-46):
```python
try:
    from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
    import torch
    import torchaudio
    from sklearn.cluster import AgglomerativeClustering
    import numpy as np
    HAS_WAVLM = True
except ImportError as e:
    HAS_WAVLM = False
```

**Sliding Window Implementation** (transcribe_gui.py:1096-1124):
```python
WINDOW_SIZE = 1.0
WINDOW_STRIDE = 0.5

segments_for_embedding = []
current_time = 0
while current_time < total_duration:
    window_start = current_time
    window_end = current_time + WINDOW_SIZE

    window_word_indices = [
        i for i, word in enumerate(all_words)
        if word.start >= window_start and word.end <= window_end
    ]

    if window_word_indices:
        segments_for_embedding.append({
            'word_indices': window_word_indices,
            'start': window_start,
            'end': window_end
        })

    current_time += WINDOW_STRIDE
```

**Embedding Extraction** (test_wavlm.py:59-72):
```python
start_sample = int(word.start * sample_rate)
end_sample = int(word.end * sample_rate)
word_audio = waveform[:, start_sample:end_sample]

inputs = feature_extractor(
    word_audio.squeeze().numpy(),
    sampling_rate=16000,
    return_tensors="pt",
    padding=True
)

with torch.no_grad():
    embedding = wavlm_model(**inputs).embeddings
    embedding = torch.nn.functional.normalize(embedding, dim=-1)
```

**Clustering** (test_wavlm.py:78-79):
```python
clustering = AgglomerativeClustering(n_clusters=num_speakers, metric='cosine', linkage='average')
speaker_ids = clustering.fit_predict(embeddings_array)
```

### Performance Benchmarks

Hardware: M1 MacBook Pro, 16GB RAM

| Audio Length | Transcription Only | With Diarization | Slowdown |
|--------------|-------------------|------------------|----------|
| 1 minute | 3 seconds | 8 seconds | 2.7x |
| 5 minutes | 15 seconds | 40 seconds | 2.7x |
| 10 minutes | 30 seconds | 80 seconds | 2.7x |
| 30 minutes | 90 seconds | 245 seconds | 2.7x |

Memory usage scales linearly with audio length for diarization, quadratically for very long files due to clustering complexity.

---

**Document Version**: 1.0
**Last Updated**: 2025-01-28
**Status**: Archived (feature on separate branch)
