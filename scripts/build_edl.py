#!/usr/bin/env python3
"""Phase 2 - Detection des coupes -> build/edl.json.

Entrees : build/words.json, build/transcript.json, build/silences.json
Sortie  : build/edl.json  = liste de segments a CONSERVER
          {start, end, reason, text}

Regles (cf. brief) :
  - silences > 700ms coupes en laissant 120ms de respiration
  - tics de langage isoles en debut de phrase (euh, hmm, bah, du coup...)
  - repetitions semantiques (TF-IDF cosine > 0.85) -> garde la meilleure prise
  - anti-hachoir : aucun segment conserve < 1.2s (fusion/suppression)
"""
import json, os, re, math
from collections import Counter

PAD = 0.120          # respiration laissee autour des silences
MIN_SEG = 1.20       # anti-hachoir
SIM_THRESH = 0.85    # repetition semantique

FILLERS = {"euh", "euhm", "hmm", "hum", "bah", "ben", "heu"}
FILLER_PHRASES = ["du coup", "en fait", "voila quoi", "genre"]

os.makedirs("build", exist_ok=True)
words = json.load(open("build/words.json"))
segments = json.load(open("build/transcript.json"))
silences = json.load(open("build/silences.json"))  # [{start,end}]
DUR = float(open("build/duration.txt").read().strip())


def norm(s):
    s = s.lower()
    s = re.sub(r"[^a-zàâäéèêëïîôöùûüç' ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---- 1. Base timeline : intervalles PARLES (hors silences longs) ----------
# On construit les "trous" a couper = silences longs, en gardant PAD de chaque cote.
cuts = []  # intervalles a supprimer (start,end)
for s in silences:
    a, b = float(s["start"]), float(s["end"])
    if (b - a) <= 0.70:
        continue
    ca, cb = a + PAD, b - PAD
    if cb - ca > 0.05:
        cuts.append([ca, cb, "silence"])

# ---- 2. Tics de langage isoles en debut de segment -------------------------
tic_cuts = []
for seg in segments:
    toks = norm(seg["text"]).split()
    if not toks:
        continue
    # mots du segment avec timings
    seg_words = [w for w in words if w["start"] >= seg["start"] - 0.01
                 and w["end"] <= seg["end"] + 0.01]
    # tic isole en tete
    if seg_words:
        first = norm(seg_words[0]["word"])
        if first in FILLERS:
            tic_cuts.append([seg_words[0]["start"], seg_words[0]["end"], "tic:%s" % first])
    # faux depart type "alors - alors donc"
    joined = norm(seg["text"])
    m = re.match(r"^(\w+)\s+\1\b", joined)
    if m and seg_words:
        tic_cuts.append([seg_words[0]["start"], seg_words[0]["end"], "faux-depart"])

# ---- 3. Repetitions semantiques : detection des PRISES MULTIPLES ------------
# Les retakes sont eclates sur plusieurs segments Whisper et reformules ; une
# cosine segment-a-segment les rate. On raisonne par "containment" de bigrammes
# de mots de contenu (stopwords retires) : si le contenu d'un segment ANTERIEUR
# se retrouve en grande partie dans un segment POSTERIEUR proche (<30s), le
# premier est une prise abandonnee -> on la coupe (le brief : garder la derniere,
# generalement la plus fluide).
STOP = set("le la les un une de des du d l et en a à au aux que qui c ce se s j "
           "elle il on ne pas plus me te son sa ses tout tous toute ça cette cet "
           "dans sur pour est sont etait était mais ou où comme si tu ta tes te "
           "je nous vous ils elles y en lui leur ne n qu quand".split())

def content_bigrams(text):
    toks = [t for t in norm(text).split() if t not in STOP and len(t) > 2]
    if len(toks) < 2:
        return set(toks)
    return set(zip(toks, toks[1:]))

def containment(a, b):
    """part des bigrammes de a presents dans b (a inclus dans b ?)"""
    if not a:
        return 0.0
    return len(a & b) / len(a)

CONTAIN_THRESH = 0.50   # >=50% du contenu du 1er reapparait dans le 2e
PROX = 30.0             # les 2 prises sont a moins de 30s

big = [content_bigrams(s["text"]) for s in segments]
rep_cuts = []
dropped = set()
for i in range(len(segments)):
    if i in dropped:
        continue
    for j in range(i + 1, len(segments)):
        if j in dropped:
            continue
        if segments[j]["start"] - segments[i]["end"] > PROX:
            break
        c = containment(big[i], big[j])
        if c >= CONTAIN_THRESH and len(big[i]) >= 3:
            # segment i (prise anterieure) abandonne au profit de j
            dropped.add(i)
            rep_cuts.append([segments[i]["start"], segments[i]["end"],
                             "prise-abandonnee(%.0f%%->#%d)" % (100 * c, j)])
            break

# ---- 4. Fusionner tous les intervalles a couper ---------------------------
all_cuts = cuts + tic_cuts + rep_cuts
all_cuts.sort()
merged = []
for c in all_cuts:
    if merged and c[0] <= merged[-1][1] + 0.02:
        merged[-1][1] = max(merged[-1][1], c[1])
        if c[2] not in merged[-1][2]:
            merged[-1][2] += "+" + c[2]
    else:
        merged.append([c[0], c[1], c[2]])

# ---- 5. Deriver les segments CONSERVES (complement des coupes) ------------
keep = []
t = 0.0
for a, b, reason in merged:
    a = max(0.0, a); b = min(DUR, b)
    if a > t + 0.01:
        keep.append({"start": round(t, 3), "end": round(a, 3)})
    t = max(t, b)
if t < DUR - 0.01:
    keep.append({"start": round(t, 3), "end": round(DUR, 3)})

# ---- 6. Anti-hachoir : fusion/suppression des fragments < MIN_SEG ---------
def seg_text(a, b):
    ws = [w["word"] for w in words if w["start"] >= a - 0.05 and w["end"] <= b + 0.05]
    return " ".join(ws).strip()

cleaned = []
for k in keep:
    dur = k["end"] - k["start"]
    if dur < MIN_SEG:
        # fusion avec le voisin precedent si le trou est petit (<0.4s), sinon drop
        if cleaned and k["start"] - cleaned[-1]["end"] < 0.4:
            cleaned[-1]["end"] = k["end"]
        else:
            continue  # supprime le fragment trop court
    else:
        cleaned.append(dict(k))

edl = []
for k in cleaned:
    edl.append({"start": round(k["start"], 3), "end": round(k["end"], 3),
                "reason": "keep", "text": seg_text(k["start"], k["end"])})

json.dump({"cuts": [{"start": round(a,3), "end": round(b,3), "reason": r}
                    for a, b, r in merged],
           "keep": edl,
           "source_duration": DUR},
          open("build/edl.json", "w"), ensure_ascii=False, indent=2)

kept = sum(k["end"] - k["start"] for k in edl)
print("=== EDL RESUME ===")
print("Source        : %6.1f s" % DUR)
print("Conserve      : %6.1f s  (%d segments)" % (kept, len(edl)))
print("Supprime      : %6.1f s  (%d coupes)" % (DUR - kept, len(merged)))
print("Reduction     : %5.1f%%" % (100 * (DUR - kept) / DUR))
print()
print("--- Passages SUPPRIMES ---")
for a, b, r in merged:
    txt = seg_text(a, b)
    print("  [%6.2f-%6.2f] %-22s %s" % (a, b, r, (txt[:60] or "(silence)")))
