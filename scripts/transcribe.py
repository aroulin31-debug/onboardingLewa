#!/usr/bin/env python3
"""Phase 1 - Transcription mot a mot (FR).

Essaie whisper-timestamped (large-v3) puis retombe sur faster-whisper.
Sortie normalisee: build/words.json  ->  [{"word","start","end"}...]
et build/transcript.json (segments phrases pour la Phase 2).
"""
import json, os, sys, subprocess

SRC = "rushes/main.mp4"
OUT_DIR = "build"
os.makedirs(OUT_DIR, exist_ok=True)


def try_whisper_timestamped():
    import whisper_timestamped as wt
    import whisper
    print("[transcribe] backend = whisper-timestamped large-v3", flush=True)
    model = wt.load_model("large-v3", device="cpu")
    result = wt.transcribe(model, SRC, language="fr",
                           vad=False, detect_disfluencies=True)
    words, segments = [], []
    for seg in result["segments"]:
        segments.append({"start": seg["start"], "end": seg["end"],
                         "text": seg["text"].strip()})
        for w in seg.get("words", []):
            words.append({"word": w["text"].strip(),
                          "start": w["start"], "end": w["end"]})
    return words, segments


def try_faster_whisper():
    from faster_whisper import WhisperModel
    print("[transcribe] backend = faster-whisper large-v3 (int8)", flush=True)
    model = WhisperModel("large-v3", device="cpu", compute_type="int8")
    seg_iter, info = model.transcribe(SRC, language="fr",
                                      word_timestamps=True, vad_filter=False)
    words, segments = [], []
    for seg in seg_iter:
        segments.append({"start": seg.start, "end": seg.end,
                         "text": seg.text.strip()})
        for w in (seg.words or []):
            words.append({"word": w.word.strip(),
                          "start": w.start, "end": w.end})
    return words, segments


def main():
    try:
        words, segments = try_whisper_timestamped()
    except Exception as e:
        print(f"[transcribe] whisper-timestamped indispo ({e}); fallback", flush=True)
        words, segments = try_faster_whisper()

    with open(f"{OUT_DIR}/words.json", "w") as f:
        json.dump(words, f, ensure_ascii=False, indent=1)
    with open(f"{OUT_DIR}/transcript.json", "w") as f:
        json.dump(segments, f, ensure_ascii=False, indent=1)
    dur = words[-1]["end"] if words else 0
    print(f"[transcribe] {len(words)} mots, {len(segments)} segments, "
          f"jusqu'a {dur:.1f}s", flush=True)


if __name__ == "__main__":
    main()
