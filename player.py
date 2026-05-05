import sounddevice as sd
import soundfile as sf
import numpy as np
import queue
import threading
import sys

AUDIO_FILE  = "input.wav"
BUFFER_SIZE = 8192
BLOCK_SIZE  = 1

def run_multithread():
    ring_buffer    = queue.Queue(maxsize=BUFFER_SIZE)
    underrun_count = 0
    stop_event     = threading.Event()

    def producer():
        """Поток 1: читает файл → кладёт в буфер"""
        with sf.SoundFile(AUDIO_FILE) as f:
            while not stop_event.is_set():
                block = f.read(BLOCK_SIZE, dtype='float32', always_2d=True)
                if len(block) == 0:
                    break
                ring_buffer.put(block)  # блокируется если буфер полон
        stop_event.set()

    def callback(outdata, frames, time, status):
        """Поток 2: забирает из буфера → отдаёт звуковой карте"""
        nonlocal underrun_count
        try:
            data = ring_buffer.get_nowait()
            if len(data) < len(outdata):
                outdata[:len(data)] = data
                outdata[len(data):] = 0
                raise sd.CallbackStop
            outdata[:] = data
        except queue.Empty:
            underrun_count += 1
            print(f"⚠ Underrun #{underrun_count}!", file=sys.stderr)
            outdata.fill(0)
            if stop_event.is_set():
                raise sd.CallbackStop

    with sf.SoundFile(AUDIO_FILE) as f:
        samplerate = f.samplerate
        channels   = f.channels

    t = threading.Thread(target=producer, daemon=True)
    t.start()

    with sd.OutputStream(samplerate=samplerate,
                         channels=channels,
                         blocksize=BLOCK_SIZE,
                         dtype='float32',
                         callback=callback):
        print(f"▶ Двухпоточный | BUFFER_SIZE={BUFFER_SIZE}")
        stop_event.wait()
        t.join()

    print(f"✅ Готово. Underrun: {underrun_count}")

run_multithread()