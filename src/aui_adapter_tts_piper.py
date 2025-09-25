
class PiperTTS:
    def __init__(self) -> None:
        self._speaking = False
    def say(self, text: str) -> None:
        self._speaking = True
        print(f"[Piper] say: {text}")
    def stop(self) -> None:
        if self._speaking: print("[Piper] stop")
        self._speaking = False
