import os
import json
import time
import sounddevice as sd
import numpy as np
from vosk import Model, KaldiRecognizer
import resampy


class StudentReceiver:
    def __init__(self, usb_mic_name="AB13X USB Audio", model_path="models/vosk-model-small-en-us-0.15"):
        # Initialize Vosk model
        print(f"[INFO] Loading Vosk model from {model_path} ...")
        self.model = Model(model_path)

        # Sampling rates
        self.samplerate = 16000
        self.pipe_path = "/tmp/studentName_pipe"
        self.usb_mic_name = usb_mic_name

        # Kaldi recognizer (default vocabulary)
        self.rec = KaldiRecognizer(self.model, self.samplerate)

        # Detect USB mic
        self.usb_mic_index = self._detect_usb_mic(self.usb_mic_name)
        dev_info = sd.query_devices(self.usb_mic_index)
        self.native_samplerate = int(dev_info['default_samplerate'])
        print(f"[INFO] USB mic '{self.usb_mic_name}' at index {self.usb_mic_index}, "
              f"native rate {self.native_samplerate} Hz")

        # Create named pipe
        if os.path.exists(self.pipe_path):
            os.remove(self.pipe_path)
        os.mkfifo(self.pipe_path)
        print(f"[INFO] Created named pipe at {self.pipe_path}")

        # Pre-warm mic
        self._prewarm_mic()

    def _detect_usb_mic(self, name):
        for i, dev in enumerate(sd.query_devices()):
            if name in dev['name'] and dev['max_input_channels'] > 0:
                return i
        raise RuntimeError(f"[ERROR] USB mic '{name}' not found")

    def _prewarm_mic(self):
        print("[INFO] Pre-warming mic...")
        try:
            s = sd.InputStream(
                device=self.usb_mic_index,
                samplerate=self.native_samplerate,
                channels=1,
                dtype='int16'
            )
            s.start()
            time.sleep(0.3)
            s.stop()
            s.close()
            print("[INFO] Mic pre-warmed successfully")
        except Exception as e:
            print(f"[WARN] Mic pre-warm failed: {e}")

    # -------------------------
    # Named pipe
    # -------------------------
    def wait_for_student(self):
        try:
            with open(self.pipe_path, 'r') as pipe:
                student_name = pipe.readline().strip()
                return student_name if student_name else None
        except Exception as e:
            print(f"[ERROR] Pipe read error: {e}")
            return None

    def start_listening(self):
        while True:
            student_name = self.wait_for_student()
            if student_name:
                print(f"[INFO] Received student: {student_name}")
                return student_name
            time.sleep(0.5)

    # -------------------------
    # Audio recording
    # -------------------------
    def record_audio(self, duration=5):
        frames_needed = int(duration * self.native_samplerate)
        collected = 0
        audio_buffer = []

        # Open mic
        for attempt in range(5):
            try:
                stream = sd.InputStream(
                    samplerate=self.native_samplerate,
                    device=self.usb_mic_index,
                    channels=1,
                    dtype='int16',
                    blocksize=1024
                )
                stream.start()
                break
            except Exception as e:
                print(f"[WARN] Mic open failed: {e}")
                time.sleep(1)
        else:
            print("[ERROR] Mic failed completely")
            return None

        try:
            while collected < frames_needed:
                data, overflowed = stream.read(1024)
                if overflowed:
                    print("[WARN] Overflow detected")
                audio_buffer.append(data)
                collected += len(data)
        finally:
            stream.stop()
            stream.close()

        if not audio_buffer:
            return None

        audio = np.concatenate(audio_buffer).flatten()
        if np.abs(audio).mean() < 50:
            return None  # silence

        # Resample to model rate
        audio_resampled = resampy.resample(
            audio.astype(np.float32),
            self.native_samplerate,
            self.samplerate
        )
        return np.array(audio_resampled, dtype=np.int16)

    # -------------------------
    # Recognition
    # -------------------------
    def recognize_audio(self, audio):
        """Recognize audio and map common keywords"""
        if self.rec.AcceptWaveform(audio.tobytes()):
            result = json.loads(self.rec.Result())
        else:
            result = json.loads(self.rec.PartialResult())

        text = result.get("text", "").strip()
        text = self.fix_common_errors(text)
        return text

    def fix_common_errors(self, text):
        """Map common mis-recognitions to 'cluj' or 'utcn'"""
        replacements = {
            "clues": "cluj",
            "clue": "cluj",
            "clooj": "cluj",
            "you teach me": "utcn",
            "you t c n": "utcn",
            "u t c n": "utcn",
            "utc n": "utcn"
        }
        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)
        return text

    # -------------------------
    # Cleanup
    # -------------------------
    def cleanup(self):
        if os.path.exists(self.pipe_path):
            os.remove(self.pipe_path)
            print(f"[INFO] Removed pipe {self.pipe_path}")