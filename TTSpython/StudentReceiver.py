import os
import stat
import tempfile
import subprocess
import json
from vosk import Model, KaldiRecognizer
import sounddevice as sd
import numpy as np
import time

class StudentReceiver:
    def __init__(self):
        # Initialize Vosk model
        self.model_path = "models/vosk-model-small-en-us-0.15"
        print(f"[INFO] Loading Vosk model from {self.model_path} ...")
        self.model = Model(self.model_path)
        self.samplerate = 16000
        self.pipe_path = "/tmp/studentName_pipe"

        # Create FIFO if it doesn't exist
        if os.path.exists(self.pipe_path):
            os.remove(self.pipe_path)  # Remove old pipe
        os.mkfifo(self.pipe_path)
        print(f"[INFO] Created named pipe at {self.pipe_path}")

    def wait_for_student(self):
        """
        Wait for student name from pipe. Blocks until data arrives.
        Returns the student name or None if pipe closes without data.
        """
        print("[INFO] Opening pipe (blocking until writer connects)...")
        try:
            # This blocks until a writer opens the other end
            with open(self.pipe_path, 'r') as pipe:
                print("[INFO] Writer connected! Reading data...")
                student_name = pipe.readline().strip()
                print(f"[DEBUG] Raw from pipe: '{student_name}'")
                return student_name if student_name else None
        except Exception as e:
            print(f"[ERROR] Pipe read error: {e}")
            return None

    def start_listening(self):
        """
        Continuously wait for student names from the pipe.
        """
        print("[INFO] Ready to receive student names via pipe...")
        while True:
            student_name = self.wait_for_student()
            if student_name:
                print(f"[INFO] Received student: {student_name}")
                return student_name
            else:
                print("[WARN] Pipe closed without data, reopening...")
                time.sleep(0.5)

    def record_audio(self, duration=5):
        """
        Record audio from microphone using sounddevice.
        """
        print(f"[INFO] Înregistrare audio pentru {duration} secunde...")
        audio = sd.rec(int(self.samplerate * duration),
                       samplerate=self.samplerate,
                       channels=1, dtype='int16')
        sd.wait()
        return np.array(audio, dtype=np.int16)

    def recognize_audio(self, audio):
        """
        Recognize Romanian speech from numpy audio array.
        """
        rec = KaldiRecognizer(self.model, self.samplerate)
        rec.AcceptWaveform(audio.tobytes())
        result = json.loads(rec.Result())
        text = result.get("text", "").strip()
        print(f"[DEBUG] Text recunoscut: '{text}'")
        return text or ""
    
    def cleanup(self):
        """Remove the named pipe"""
        if os.path.exists(self.pipe_path):
            os.remove(self.pipe_path)
            print(f"[INFO] Removed pipe {self.pipe_path}")