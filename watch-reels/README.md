# watch-reels — analyse en lot de Reels Instagram

Traite en une fois tous les Reels listés dans `reels.txt` via la skill `watch`
(téléchargement + extraction des images de scènes + transcription depuis les
sous-titres). **À lancer sur ta machine locale** — l'environnement cloud de
Claude Code bloque Instagram au niveau réseau.

## Prérequis (une seule fois)

```bash
# 1. Outils système
brew install ffmpeg yt-dlp

# 2. Cookies Instagram pour yt-dlp (sois connecté à Instagram dans Firefox)
mkdir -p ~/.config/yt-dlp
echo '--cookies-from-browser firefox' >> ~/.config/yt-dlp/config
# (remplace firefox par chrome si tu préfères — Firefox est plus fiable)
```

## Lancer

```bash
cd watch-reels
./watch-reels.sh
```

Options :

```bash
./watch-reels.sh mes_liens.txt   # utiliser un autre fichier de liens
SLEEP=40 ./watch-reels.sh        # pause plus longue entre Reels (anti rate-limit)
INTENT="analyser l'accroche" ./watch-reels.sh   # change l'objectif d'analyse
```

## Ce que ça produit

Pour chaque Reel, un dossier `out/NN_<id>/` contenant :

- les images des scènes (`*.jpg`)
- `report.md` — rapport structuré (TL;DR, moments clés, hook 0-10s…)
- `watch-output.md` — sortie brute de la skill
- `error.log` — en cas d'échec

Un récapitulatif est écrit dans `out/SUMMARY.md`.

## Étape suivante : l'analyse par Claude

Le script fait la partie mécanique (télécharger + extraire les images). Pour
l'**analyse** (lire les images, remplir les sections narratives du `report.md`),
ouvre **Claude Code dans ce dépôt** et demande-lui d'analyser les dossiers de
`out/` — il lit les `.jpg` et complète chaque rapport.

## Notes

- **Sans Whisper** : tu obtiens les images + le texte incrusté à l'écran, mais
  pas la transcription de l'audio parlé. Pour l'activer, ajoute une clé dans
  `~/.config/watch/.env` : `echo 'GROQ_API_KEY=...' >> ~/.config/watch/.env`
  (clé gratuite sur console.groq.com) et retire `--no-whisper` du script.
- **Idempotent** : un Reel déjà traité (avec `report.md`) est sauté. Tu peux
  relancer après une coupure, il reprend où il s'était arrêté.
- **Rate-limit Instagram** : si tu vois des erreurs `429`, augmente `SLEEP`.
