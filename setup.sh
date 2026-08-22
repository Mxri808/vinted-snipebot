#!/bin/bash
# Vinted Snipebot - Quick Start Script

echo "========================================="
echo "🚀 VINTED SNIPEBOT SETUP"
echo "========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 nicht gefunden! Bitte installiere Python3."
    echo "   macOS: brew install python3"
    echo "   Ubuntu: sudo apt install python3"
    exit 1
fi

echo "✅ Python3 gefunden: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installiere Abhängigkeiten..."
pip3 install -r requirements.txt

echo ""
echo "========================================="
echo "📱 TELEGRAM BOT SETUP"
echo "========================================="
echo ""
echo "1. Öffne Telegram und suche nach @BotFather"
echo "2. Sende /newbot und erstelle einen neuen Bot"
echo "3. Kopiere den Bot-Token"
echo "4. Füge den Token in config.json ein"
echo ""
echo "5. Finde deine Chat-ID:"
echo "   - Sende eine Nachricht an deinen Bot"
echo "   - Öffne: https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates"
echo "   - Kopiere die chat.id"
echo "6. Füge die Chat-ID in config.json ein"
echo ""
echo "========================================="
echo "📝 CONFIG ANPASSEN"
echo "========================================="
echo ""
echo "Öffne config.json und passe folgende Werte an:"
echo "  - telegram_bot_token: Dein Bot-Token"
echo "  - telegram_chat_id: Deine Chat-ID"
echo "  - max_price: Maximaler Preis (Standard: 50€)"
echo "  - check_interval: Suchintervall in Sekunden (Standard: 180)"
echo ""
echo "========================================="
echo "▶️  BOT STARTEN"
echo "========================================="
echo ""
echo "Starte den Bot mit:"
echo "  python3 vinted_snipebot.py"
echo ""
echo "Oder im Hintergrund:"
echo "  nohup python3 vinted_snipebot.py > snipebot.log 2>&1 &"
echo ""
echo "========================================="
echo "✅ SETUP ABGESCHLOSSEN!"
echo "========================================="
