# core/models.py
from pydantic import BaseModel
from typing import Dict
from enum import Enum

class EditionType(Enum):
    SIMPLE = "arabic2"
    UTHMANI = "arabic1"
    ENGLISH = "english"

class SurahInfo(BaseModel):
    surah_name: str
    surah_name_arabic: str
    total_ayah: int
    revelation_place: str
    surah_number: int
    audio: Dict[str, Dict[str, str]]

class Ayah(BaseModel):
    number: int
    text: str
    arabic_simple: str
    arabic_uthmani: str