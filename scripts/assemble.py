#!/usr/bin/env python3
"""Phase 3 - Assemblage -> build/rough_cut.mp4.

Coupe franche frame-accurate via le filtre concat (A+V ensemble => sync
parfaite), avec micro-fades audio de 10ms a chaque raccord pour supprimer
les clics sans decaler le lip-sync. Un seul re-encodage (CRF 16).
"""
import json, subprocess, os

SRC = "rushes/main.mp4"
OUT = "build/rough_cut.mp4"
FADE = 0.010  # micro-fade audio anti-clic

keep = json.load(open("build/edl.json"))["keep"]

vparts, aparts, vlabels, alabels = [], [], [], []
for i, k in enumerate(keep):
    a, b = k["start"], k["end"]
    d = b - a
    vparts.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]")
    # fade in au debut + fade out a la fin de chaque segment
    aparts.append(
        f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={FADE},afade=t=out:st={max(0,d-FADE):.3f}:d={FADE}[a{i}]"
    )
    vlabels.append(f"[v{i}]")
    alabels.append(f"[a{i}]")

n = len(keep)
fg = ";".join(vparts + aparts)
fg += ";" + "".join(vlabels) + f"concat=n={n}:v=1:a=0[v]"
fg += ";" + "".join(alabels) + f"concat=n={n}:v=0:a=1[a]"

cmd = [
    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
    "-i", SRC,
    "-filter_complex", fg,
    "-map", "[v]", "-map", "[a]",
    "-c:v", "libx264", "-crf", "16", "-preset", "medium",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart", OUT,
]
subprocess.run(cmd, check=True)
# verif
dur = subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "csv=p=0", OUT]).decode().strip()
size = os.path.getsize(OUT)
print(f"[assemble] {OUT}  duree={float(dur):.2f}s  taille={size/1e6:.1f}MB  segments={n}")
