#!/usr/bin/env python3
"""Phase 4 - Sous-titres recales sur la timeline post-coupes.

Remappe les timestamps mot-a-mot sur la nouvelle timeline (erreur classique:
reutiliser les timings d'origine -> decalage), puis groupe en cartons lisibles.
Sortie: export/subtitles.srt
Regles: <=32 car/ligne, <=2 lignes, 1-4s, jamais <1s, coupe aux frontieres
syntaxiques.
"""
import json, os, re

os.makedirs("export", exist_ok=True)
words = json.load(open("build/words.json"))
keep = json.load(open("build/edl.json"))["keep"]

MAXLINE = 32
MAXCHARS = 52      # tient en 2 lignes de <=32 apres wrap equilibre
MAXDUR = 3.5
MINDUR = 1.0
GAP = 0.45         # nouveau carton si trou > GAP

# ---- 1. Remap mots -> nouvelle timeline -----------------------------------
mapped = []
new_t = 0.0
for k in keep:
    a, b = k["start"], k["end"]
    for w in words:
        if w["start"] >= a - 0.001 and w["end"] <= b + 0.001:
            tok = w["word"].replace("[*]", "").strip()
            if tok:
                mapped.append({"w": tok,
                               "s": new_t + (w["start"] - a),
                               "e": new_t + (w["end"] - a)})
    new_t += (b - a)
mapped.sort(key=lambda x: x["s"])

# ---- 2. Groupage en cartons (frontieres syntaxiques) -----------------------
def clean(text):
    return re.sub(r"\s+([,.!?;:])", r"\1", " ".join(text).strip())

cues, cur = [], []
for m in mapped:
    if cur:
        prev = cur[-1]
        cand = clean([x["w"] for x in cur] + [m["w"]])
        gap = m["s"] - prev["e"]
        dur = prev["e"] - cur[0]["s"]
        if len(cand) > MAXCHARS or dur > MAXDUR or gap > GAP or re.search(r"[.!?]$", prev["w"]):
            cues.append({"s": cur[0]["s"], "e": cur[-1]["e"],
                         "text": clean([x["w"] for x in cur])})
            cur = []
    cur.append(m)
if cur:
    cues.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": clean([x["w"] for x in cur])})

# ---- 3. Anti-chevauchement --------------------------------------------------
for i in range(len(cues) - 1):
    if cues[i]["e"] > cues[i + 1]["s"] - 0.03:
        cues[i]["e"] = cues[i + 1]["s"] - 0.05

# ---- 4. Cartons < MINDUR ----------------------------------------------------
#  a) prolonger dans la pause suivante ; b) sinon fusion MEME PHRASE avec le
#  carton precedent (cas des fins de phrase courtes : "...le pont.") ; c) sinon
#  fusion meme-phrase avec le suivant. Jamais de fusion en travers d'un point.
MERGE_MAX = 60  # tient en 2 lignes apres wrap
i = 0
while i < len(cues):
    dur = cues[i]["e"] - cues[i]["s"]
    if dur >= MINDUR:
        i += 1; continue
    limit = (cues[i + 1]["s"] - 0.05) if i + 1 < len(cues) else cues[i]["s"] + MINDUR
    cues[i]["e"] = min(cues[i]["s"] + MINDUR, max(cues[i]["e"], limit))
    if cues[i]["e"] - cues[i]["s"] >= MINDUR - 1e-3:
        i += 1; continue
    prev_open = i > 0 and not re.search(r"[.!?]$", cues[i - 1]["text"])
    if prev_open and len(cues[i - 1]["text"] + " " + cues[i]["text"]) <= MERGE_MAX:
        cues[i - 1]["e"] = cues[i]["e"]
        cues[i - 1]["text"] = (cues[i - 1]["text"] + " " + cues[i]["text"]).strip()
        cues.pop(i); i -= 1; continue
    if i + 1 < len(cues) and not re.search(r"[.!?]$", cues[i]["text"]) \
       and len(cues[i]["text"] + " " + cues[i + 1]["text"]) <= MERGE_MAX:
        cues[i + 1]["s"] = cues[i]["s"]
        cues[i + 1]["text"] = (cues[i]["text"] + " " + cues[i + 1]["text"]).strip()
        cues.pop(i); continue
    # d) dernier recours : emprunter du lead-in au carton precedent (qui a du mou)
    if i > 0:
        deficit = MINDUR - (cues[i]["e"] - cues[i]["s"])
        new_start = cues[i]["s"] - deficit
        if new_start >= cues[i - 1]["s"] + MINDUR:
            cues[i - 1]["e"] = new_start - 0.001
            cues[i]["s"] = new_start
    i += 1

# ---- 5. Wrap equilibre en <=2 lignes de <=32 car ---------------------------
def wrap2(text):
    ws = text.split()
    # cherche le point de coupe qui minimise l'ecart entre 2 lignes, chacune<=32
    best = None
    for k in range(1, len(ws)):
        l1, l2 = " ".join(ws[:k]), " ".join(ws[k:])
        if len(l1) <= MAXLINE and len(l2) <= MAXLINE:
            score = abs(len(l1) - len(l2))
            if best is None or score < best[0]:
                best = (score, l1 + "\n" + l2)
    if best:
        return best[1]
    if len(text) <= MAXLINE:
        return text
    # secours: coupe gloutonne
    l1 = ""
    for j, w in enumerate(ws):
        if len((l1 + " " + w).strip()) <= MAXLINE:
            l1 = (l1 + " " + w).strip()
        else:
            return l1 + "\n" + " ".join(ws[j:])
    return text

def ts(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    ms = round((t - int(t)) * 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)

with open("export/subtitles.srt", "w") as f:
    for i, c in enumerate(cues, 1):
        f.write("%d\n%s --> %s\n%s\n\n" % (i, ts(c["s"]), ts(c["e"]), wrap2(c["text"])))

# ---- 6. ASS avec PlayRes pinned = pixels reels (rendu previsible) ----------
def ts_ass(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Def,DejaVu Sans,46,&H00FFFFFF,&H00FFFFFF,&H55000000,&H55000000,1,0,0,0,100,100,0,0,3,16,0,2,90,90,200,1

[Events]
Format: Layer, Start, End, Style, MarginL, MarginR, MarginV, Effect, Text
"""
with open("export/subtitles.ass", "w") as f:
    f.write(ASS_HEADER)
    for c in cues:
        txt = wrap2(c["text"]).replace("\n", "\\N")
        f.write("Dialogue: 0,%s,%s,Def,,,,,%s\n" %
                (ts_ass(c["s"]), ts_ass(c["e"]), txt))

lines = [l for c in cues for l in wrap2(c["text"]).split("\n")]
print(f"[subtitles] {len(cues)} cartons -> export/subtitles.srt")
print(f"[subtitles] ligne max: {max(len(l) for l in lines)} car (limite {MAXLINE})")
print(f"[subtitles] over-32: {sum(1 for l in lines if len(l) > MAXLINE)} lignes")
print(f"[subtitles] duree: min={min(c['e']-c['s'] for c in cues):.2f}s "
      f"max={max(c['e']-c['s'] for c in cues):.2f}s")
