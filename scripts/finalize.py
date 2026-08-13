#!/usr/bin/env python3
"""Phase 6 - Finition -> export/final_vertical.mp4 (une seule generation).

Depuis la SOURCE directement (evite une 2e generation de perte) :
  video : trim/concat (EDL) -> delogo (watermark) -> sous-titres ASS (Inter)
  audio : atrim/concat + micro-fades anti-clic -> loudnorm -14 LUFS (2-passe)
Encodage final : H.264 CRF18 yuv420p +faststart, AAC 192k.
"""
import json, subprocess, os

SRC = "rushes/main.mp4"
OUT = "export/final_vertical.mp4"
os.makedirs("export", exist_ok=True)
FADE = 0.010

# delogo watermark clideo.com (bas-droite)
DELOGO = "delogo=x=728:y=1806:w=348:h=98"
# loudnorm passe-1 mesuree sur le montage (cf. ffmpeg loudnorm print_format=json)
LOUDNORM = ("loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=-9.22:measured_TP=1.77:"
            "measured_LRA=2.20:measured_thresh=-19.42:offset=0.20:linear=true")

keep = json.load(open("build/edl.json"))["keep"]
vparts, aparts, vl, al = [], [], [], []
for i, k in enumerate(keep):
    a, b = k["start"], k["end"]; d = b - a
    vparts.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]")
    aparts.append(f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d={FADE},afade=t=out:st={max(0,d-FADE):.3f}:d={FADE}[a{i}]")
    vl.append(f"[v{i}]"); al.append(f"[a{i}]")

n = len(keep)
fg = ";".join(vparts + aparts)
fg += ";" + "".join(vl) + f"concat=n={n}:v=1:a=0[vc]"
fg += f";[vc]{DELOGO}[vd];[vd]ass=export/subtitles.ass[v]"
fg += ";" + "".join(al) + f"concat=n={n}:v=0:a=1[ac]"
fg += f";[ac]{LOUDNORM},aresample=44100[a]"

cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", SRC,
       "-filter_complex", fg, "-map", "[v]", "-map", "[a]",
       "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT]
subprocess.run(cmd, check=True)
print(f"[finalize] {OUT} ecrit ({os.path.getsize(OUT)/1e6:.1f} MB)")
