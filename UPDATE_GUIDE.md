# Vinted Snipebot - Auto-Update Guide

## So funktioniert das Auto-Update:

```
Du änderst lokal → Push auf GitHub → Server holt Updates automatisch
```

---

## Einmaliges Setup (5 Minuten):

### 1. GitHub Repository erstellen

```bash
# Auf deinem Mac:
cd ~/Projects/Resell
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/DEIN_USERNAME/vinted-snipebot.git
git push -u origin main
```

### 2. Server einrichten

```bash
# SSH auf Server:
ssh -i ~/.ssh/oracle_key ubuntu@<DEINE_IP>

# Setup Script ausführen:
bash server_setup.sh
```

### 3. Config anpassen

```bash
# Auf Server:
nano ~/vinted-bot/config.json

# Telegram Token und Chat-ID eintragen
```

### 4. Bot starten

```bash
bash bot.sh start
```

---

## Updates durchführen:

### Wenn du Änderungen machst:

```bash
# 1. Änderungen speichern
cd ~/Projects/Resell
git add .
git commit -m "Neue Funktion"
git push

# 2. Fertig! Server updated sich automatisch in ~5 Minuten
```

### Manuelles Update (sofort):

```bash
# Auf Server:
bash bot.sh update
```

---

## Nützliche Befehle:

```bash
# Bot starten
bash bot.sh start

# Bot stoppen
bash bot.sh stop

# Bot neustarten
bash bot.sh restart

# Status prüfen
bash bot.sh status

# Logs anzeigen
bash bot.sh logs

# Manuelles Update
bash bot.sh update
```

---

## Dateien auf dem Server:

```
~/vinted-bot/
├── vinted_snipebot.py    # Hauptbot
├── config.json           # Konfiguration
├── updater.py            # Auto-Updater
├── seen_items.json       # Bereits gesehene Items
├── snipebot.log          # Bot-Logs
└── requirements.txt      # Dependencies
```

---

## Auto-Update Process:

```
┌─────────────────────────────────────────────────────────┐
│  Dein Mac                    GitHub              Server  │
│  ─────────────────────────────────────────────────────  │
│  Änderung machen  ──→  Push  ──→  Pull (automatisch)   │
│                                          │              │
│                                          ▼              │
│                                    Bot neustartet       │
└─────────────────────────────────────────────────────────┘
```

---

## Fehlerbehebung:

| Problem | Lösung |
|---------|--------|
| Bot startet nicht | `journalctl -u vinted-bot -n 50` |
| Kein Update | `bash bot.sh update` |
| Server nicht erreichbar | Oracle Cloud Dashboard prüfen |
| Bot gestoppt | `bash bot.sh start` |
