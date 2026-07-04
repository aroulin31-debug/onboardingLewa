#!/usr/bin/env bash
#
# watch-reels.sh — enchaîne tous les Reels listés dans reels.txt à travers la
# skill `watch` (téléchargement + images des scènes + transcription sous-titres).
#
# À lancer SUR TA MACHINE (pas dans l'environnement cloud, qui bloque Instagram).
#
# Prérequis (une seule fois) :
#   brew install ffmpeg yt-dlp
#   mkdir -p ~/.config/yt-dlp && echo '--cookies-from-browser firefox' >> ~/.config/yt-dlp/config
#   (sois connecté à Instagram dans Firefox — ou remplace firefox par chrome)
#
# Usage :
#   cd watch-reels
#   ./watch-reels.sh                 # traite reels.txt, sort dans ./out
#   ./watch-reels.sh mes_liens.txt   # autre fichier de liens
#   SLEEP=30 ./watch-reels.sh        # change la pause anti rate-limit (défaut 25s)
#
# Idempotent : un Reel déjà traité (report.md présent) est sauté. Relance sans
# crainte après une coupure — il reprend où il s'est arrêté.

set -uo pipefail

# --- Résolution des chemins -------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WATCH_PY="$REPO_ROOT/.claude/skills/watch/scripts/watch.py"

LINKS_FILE="${1:-$SCRIPT_DIR/reels.txt}"
OUT_DIR="$SCRIPT_DIR/out"
SLEEP="${SLEEP:-25}"          # pause entre deux Reels (anti 429 Instagram)
INTENT="${INTENT:-analyser le hook (0-10s), le message cle et le texte incruste a l ecran}"

# --- Vérifications préalables ------------------------------------------------
fail=0
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 introuvable."; fail=1; }
command -v ffmpeg  >/dev/null 2>&1 || { echo "❌ ffmpeg introuvable — 'brew install ffmpeg'."; fail=1; }
command -v yt-dlp  >/dev/null 2>&1 || { echo "❌ yt-dlp introuvable — 'brew install yt-dlp'."; fail=1; }
[ -f "$WATCH_PY" ]                  || { echo "❌ watch.py introuvable à $WATCH_PY (mauvais dossier ?)."; fail=1; }
[ -f "$LINKS_FILE" ]               || { echo "❌ Fichier de liens introuvable : $LINKS_FILE"; fail=1; }
[ "$fail" -eq 0 ] || exit 1

mkdir -p "$OUT_DIR"
SUMMARY="$OUT_DIR/SUMMARY.md"
echo "# Résumé du traitement des Reels" > "$SUMMARY"
echo "" >> "$SUMMARY"
echo "| # | Reel | Statut | Dossier |" >> "$SUMMARY"
echo "|---|------|--------|---------|" >> "$SUMMARY"

# --- Boucle principale -------------------------------------------------------
i=0
ok=0
ko=0
skipped=0
while IFS= read -r url || [ -n "$url" ]; do
  # Ignore commentaires / lignes vides
  url="$(echo "$url" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [ -z "$url" ] && continue
  case "$url" in \#*) continue ;; esac

  i=$((i+1))
  # Identifiant du Reel (dernier segment non vide de l'URL)
  slug="$(echo "$url" | sed -E 's#/+$##; s#.*/##')"
  [ -z "$slug" ] && slug="reel_$i"
  work="$OUT_DIR/$(printf '%02d' "$i")_$slug"

  printf '\n=== [%d] %s ===\n' "$i" "$url"

  if [ -f "$work/report.md" ]; then
    echo "↩︎  déjà traité — on saute."
    echo "| $i | $slug | ⏭️ déjà fait | \`$(basename "$work")\` |" >> "$SUMMARY"
    skipped=$((skipped+1))
    continue
  fi

  mkdir -p "$work"
  # 2 tentatives (Instagram renvoie parfois un 429 transitoire)
  status="échec"
  for attempt in 1 2; do
    if python3 "$WATCH_PY" "$url" \
        --no-whisper \
        --out-dir "$work" \
        --intent "$INTENT" \
        > "$work/watch-output.md" 2> "$work/error.log"; then
      status="ok"
      break
    fi
    echo "⚠️  tentative $attempt échouée (voir $work/error.log)."
    [ "$attempt" -eq 1 ] && { echo "   nouvelle tentative dans ${SLEEP}s..."; sleep "$SLEEP"; }
  done

  if [ "$status" = "ok" ]; then
    echo "✅  OK → $work"
    echo "| $i | $slug | ✅ OK | \`$(basename "$work")\` |" >> "$SUMMARY"
    ok=$((ok+1))
  else
    echo "❌  Échec définitif → voir $work/error.log"
    tail -3 "$work/error.log" 2>/dev/null | sed 's/^/     /'
    echo "| $i | $slug | ❌ échec | \`$(basename "$work")\` |" >> "$SUMMARY"
    ko=$((ko+1))
  fi

  # Pause anti rate-limit avant le prochain (sauf si c'était le dernier)
  echo "   pause ${SLEEP}s..."
  sleep "$SLEEP"
done < "$LINKS_FILE"

# --- Bilan -------------------------------------------------------------------
printf '\n────────────────────────────────\n'
printf 'Terminé : %d OK · %d échec · %d sautés (total %d)\n' "$ok" "$ko" "$skipped" "$i"
printf 'Résultats dans : %s\n' "$OUT_DIR"
printf 'Récapitulatif  : %s\n' "$SUMMARY"
printf '\nProchaine étape : ouvre Claude Code dans ce dépôt et demande-lui\n'
printf 'd analyser les images de chaque dossier de %s\n' "$OUT_DIR"
printf '(chaque dossier contient les frames .jpg + un report.md à remplir).\n'
