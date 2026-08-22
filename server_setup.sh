#!/bin/bash
# Vinted Snipebot - Server Setup Script
# Run this on your Oracle Cloud (or any Linux server)

set -e

echo "========================================="
echo "🚀 VINTED SNIPEBOT - SERVER SETUP"
echo "========================================="
echo ""

# 1. System updates
echo "📦 1/7 System Updates installieren..."
sudo apt update && sudo apt upgrade -y

# 2. Install Python & dependencies
echo "🐍 2/7 Python installieren..."
sudo apt install python3 python3-pip git -y

# 3. Create project directory
echo "📁 3/7 Projektverzeichnis erstellen..."
mkdir -p ~/vinted-bot
cd ~/vinted-bot

# 4. Clone or copy files
echo "📥 4/7 Bot-Dateien laden..."
if [ -d ".git" ]; then
    echo "   Repository existiert bereits, Updates laden..."
    git pull
else
    echo "   ❌ Bitte zuerst Repository erstellen oder Dateien hochladen!"
    echo "   Option A: git clone <DEIN_REPO> ."
    echo "   Option B: scp vinted_snipebot.py config.json updater.py server:~/vinted-bot/"
    echo ""
    read -p "   Drücke Enter wenn du die Dateien hochgeladen hast..."
fi

# 5. Install Python dependencies
echo "📚 5/7 Python Dependencies installieren..."
pip3 install requests

# 6. Create systemd service for bot
echo "⚙️ 6/7 Bot Service erstellen..."
sudo tee /etc/systemd/system/vinted-bot.service > /dev/null <<EOF
[Unit]
Description=Vinted Snipebot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/vinted-bot
ExecStart=/usr/bin/python3 -u vinted_snipebot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 7. Create systemd service for updater
echo "🔄 7/7 Auto-Updater Service erstellen..."
sudo tee /etc/systemd/system/vinted-updater.service > /dev/null <<EOF
[Unit]
Description=Vinted Snipebot Auto-Updater
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/vinted-bot
ExecStart=/usr/bin/python3 -u updater.py
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
echo "🚀 Services aktivieren..."
sudo systemctl daemon-reload
sudo systemctl enable vinted-bot
sudo systemctl enable vinted-updater

echo ""
echo "========================================="
echo "✅ SETUP ABGESCHLOSSEN!"
echo "========================================="
echo ""
echo "Starte die Services mit:"
echo "  sudo systemctl start vinted-bot"
echo "  sudo systemctl start vinted-updater"
echo ""
echo "Oder beides zusammen:"
echo "  sudo systemctl start vinted-bot vinted-updater"
echo ""
echo "Status prüfen:"
echo "  sudo systemctl status vinted-bot"
echo "  sudo systemctl status vinted-updater"
echo ""
echo "Logs anzeigen:"
echo "  journalctl -u vinted-bot -f"
echo "  journalctl -u vinted-updater -f"
echo ""
echo "========================================="
