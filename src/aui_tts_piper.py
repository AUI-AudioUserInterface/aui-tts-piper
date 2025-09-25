# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations
import asyncio
import importlib.util
from typing import Optional, AsyncIterator, Any

from auicommon.audio.types import PcmAudio
# optional, falls vorhanden (kleine Helfer für Normalisierung):
try:
    from auicommon.audio.convert import normalize_to_canon, CANON_FORMAT
except Exception:
    normalize_to_canon = None
    CANON_FORMAT = None  # type: ignore

# Hinweis:
# - Dieses Modul gehört NICHT in aui-core, sondern in ein separates Paket 'aui-tts-piper' (GPLv3).
# - aui-core lädt es dynamisch über Entry-Points oder Registry. Keine harte Abhängigkeit im Core!

class PiperTTS:
    """
    Asynchroner Piper-TTS-Wrapper:
    - preload(): Modelle/Engine initialisieren (optional)
    - synth(text): PcmAudio zurückgeben (kanonisches PCM bevorzugt)
    - say(text): Fallback/Komfortmethode (ruft synth(); Abspielen macht der Core/AudioSink)
    - stop(): Synthese/Abspiel abbrechen (sofern Engine-API vorhanden)

    WICHTIG (Lizenz): Diese Datei steht unter GPLv3, weil sie für Piper geschrieben ist.
    """

    def __init__(self, model: Optional[str] = None, voice: Optional[str] = None,
                 sample_rate: int = 22050, **kwargs: Any) -> None:
        self._model = model
        self._voice = voice
        self._rate = sample_rate
        self._engine = None  # echte Piper-Engine/Session
        self._stopped = False
        self._kw = kwargs

    # ---------- Public API (async) ----------

    async def preload(self) -> None:
        """Optional: Engine/Model laden. Wird von manchen Runtimes vorab aufgerufen."""
        self._require_piper()
        # echte Initialisierung in Thread ausführen, um Eventloop nicht zu blockieren
        await asyncio.to_thread(self._init_blocking)

    async def synth(self, text: str, cancel: Optional["CancellationToken"]=None) -> PcmAudio:
        """
        Text → PCM (PcmAudio). Die eigentliche Audioausgabe macht später der AudioSink.
        """
        self._require_piper()
        self._stopped = False
        # Blockierende Synthese in Thread
        pcm = await asyncio.to_thread(self._synth_blocking, text, cancel)
        # Bei Bedarf auf kanonisches Format normalisieren (s16le/16kHz/mono)
        if normalize_to_canon is not None:
            try:
                return normalize_to_canon(pcm)
            except Exception:
                pass
        # Fallback: ungeändert zurück
        return pcm

    async def say(self, text: str, cancel: Optional["CancellationToken"]=None) -> None:
        """
        Komfort: synth() aufrufen. Das resultierende PCM muss der Core/AudioSink abspielen.
        (Wenn dein aktueller Core direktem 'say()' Ton erwartet, passe ihn an: erst synth(), dann play().)
        """
        _ = await self.synth(text, cancel=cancel)
        # Hier KEIN Abspielen – das macht der AudioSink im Core.

    async def stop(self) -> None:
        """Synthese abbrechen (sofern Engine-API vorhanden)."""
        self._stopped = True
        # Falls die Piper-Engine eine Stop-API hat, hier über to_thread aufrufen.
        # await asyncio.to_thread(self._engine.stop)  # Beispiel

    # ---------- Intern (blockierend) ----------

    def _init_blocking(self) -> None:
        """Engine laden; reale Piper-Initialisierung hier."""
        # Beispiel (Pseudo-Code):
        # import piper
        # self._engine = piper.Engine(model=self._model, voice=self._voice, **self._kw)
        pass

    def _synth_blocking(self, text: str, cancel: Optional["CancellationToken"]) -> PcmAudio:
        """Blockierende Piper-Synthese. Gibt PcmAudio (PCM) zurück."""
        if self._stopped:
            # leeres PCM zurückgeben
            return PcmAudio(data=b"", rate=self._rate, channels=1, width=2)

        # --- Pseudo-Implementierung: ECHT hier Piper aufrufen ---
        # from piper import synth  # Beispiel, realer API-Name kann abweichen
        # raw_pcm_bytes, sr = synth(text, model=self._model, voice=self._voice)
        # if self._stopped or (cancel and cancel.is_cancelled): ...
        # return PcmAudio(data=raw_pcm_bytes, rate=sr, channels=1, width=2)

        # Platzhalter/Dummy (1/10 Sek. Stille bei self._rate):
        n_samples = int(self._rate * 0.1)
        silence = b"\x00\x00" * n_samples  # s16le mono
        return PcmAudio(data=silence, rate=self._rate, channels=1, width=2)

    # ---------- Laufzeit-Check & Registrierung ----------

    def _require_piper(self) -> None:
        """
        Prüft, ob Piper installiert ist. Gibt hilfreichen Hinweis statt ImportError.
        """
        candidates = ["piper", "piper_tts", "piper-tts"]
        if not any(importlib.util.find_spec(n) for n in candidates if isinstance(n, str)):
            raise RuntimeError(
                "Piper-TTS ist nicht installiert. Bitte separat installieren, z. B.:\n"
                "  pip install piper-tts\n"
                "Achtung: Piper steht unter GPLv3; die Nutzung kann GPL-Pflichten auslösen."
            )

# Optional: Side-Effect-Registrierung (nur falls ihr neben Entry-Points auch eine Registry nutzt)
try:
    from auicore.services.tts import factory as _f  # type: ignore
    if hasattr(_f, "register"):
        _f.register("piper", lambda **kw: PiperTTS(**kw))  # type: ignore[arg-type]
    elif hasattr(_f, "REGISTRY"):
        _f.REGISTRY["piper"] = lambda **kw: PiperTTS(**kw)  # type: ignore[attr-defined,index]
except Exception:
    pass
