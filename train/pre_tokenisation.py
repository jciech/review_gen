import json, re, pathlib, itertools
from collections import Counter
import os

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.absolute()

RAW_PATH = PROJECT_ROOT / "master.json"
TEXT_PATH = PROJECT_ROOT / "reviews.txt"  # one line per review
VOCAB_SIZE = 8000  # fits into the 5‑10 k window

with RAW_PATH.open() as f:
    data = json.load(f)

clean = lambda s: re.sub(r"\s+", " ", s).strip()

profile_patterns = [
    r"Local Guide\s*·\s*\d+\s*reviews",
    r"\d+\s*reviews\s*·\s*\d+\s*photos",
    r"\d+\s*photos\s*·\s*\d+\s*reviews",
    r"·\s*\d+\s*photos",
    r"·\s*\d+\s*contributions",
]

profile_regex = re.compile("|".join(profile_patterns), re.IGNORECASE)

texts = []
for r in data:
    if not r.get("text"):
        continue

    text = clean(r["text"])

    if profile_regex.search(text):
        continue

    texts.append(text)

lens = [len(t.split()) for t in texts]
print(f"{len(texts)=}, median_tokens={sorted(lens)[len(lens)//2]}")

texts = list(dict.fromkeys(texts))

TEXT_PATH.write_text("\n".join(texts), encoding="utf-8")
print("Wrote clean corpus to", TEXT_PATH.resolve())
print(f"Filtered out reviews matching profile information patterns")
