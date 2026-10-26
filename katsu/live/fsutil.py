"""
Veilig een bestand vervangen op Windows.

Op Windows mislukt os.replace met "Access is denied" (PermissionError, WinError 5) als een ander programma het
doelbestand op dat moment open heeft — bv. de waakhond of de verzamelaar die status.json of orders.json leest.
Dat duurt meestal maar een fractie van een seconde. Daarom: een paar keer opnieuw proberen met een korte pauze.
Lukt het na alle pogingen nog niet, dan gaat de fout gewoon door (zoals vroeger).
"""
from __future__ import annotations

import os
import time

TRIES = 20          # samen ±2 seconden
WAIT_S = 0.1


def replace_retry(tmp: str, path: str, tries: int = TRIES, wait: float = WAIT_S, _replace=os.replace, _sleep=time.sleep):
    for i in range(tries):
        try:
            _replace(tmp, path)
            return i + 1                 # aantal pogingen (voor de tests)
        except PermissionError:
            if i == tries - 1:
                raise
            _sleep(wait)
