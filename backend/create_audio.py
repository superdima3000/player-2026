import sys

import numpy as np
import wave as wav_work


def create_one_freq_audio(freq, SMPL_RATE=44100, seconds=3, norma=32767):
    arr = np.linspace(0, seconds, seconds * SMPL_RATE,False )
    wave = np.sin(2 * freq * arr * np.pi)
    wave *= norma / np.max(np.abs(wave))
    wave = wave.astype(np.int16)
    return wave


def create_tester(sec, freq, mode=2):
    with wav_work.open('../test.wav', mode='wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(44100)
        norma = (2 ** (15 - mode))
        wav_file.writeframes(create_one_freq_audio(freq, seconds=sec, norma=norma))
        return 'test.wav'


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Введите время и частоту теста через пробел:")
        create_tester(*map(int, input().split(' ')))
    else:
        create_tester(*map(int, sys.argv[1:3]))
    print("\n!!! Successful !!!\n'test.wav' has been created\n")


x = ["x" for i in range(6)]