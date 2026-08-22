#!/bin/bash
# Quick commands for managing the bot on server

case "$1" in
    "start")
        echo "🚀 Starte Bot..."
        sudo systemctl start vinted-bot vinted-updater
        echo "✅ Gestartet!"
        ;;
    "stop")
        echo "🛑 Stoppe Bot..."
        sudo systemctl stop vinted-bot vinted-updater
        echo "✅ Gestoppt!"
        ;;
    "restart")
        echo "🔄 Starte Bot neu..."
        sudo systemctl restart vinted-bot vinted-updater
        echo "✅ Neugestartet!"
        ;;
    "status")
        echo "📊 Bot Status:"
        sudo systemctl status vinted-bot --no-pager
        echo ""
        echo "📊 Updater Status:"
        sudo systemctl status vinted-updater --no-pager
        ;;
    "logs")
        echo "📋 Bot Logs (letzte 50 Zeilen):"
        journalctl -u vinted-bot -n 50 --no-pager
        ;;
    "update")
        echo "🔄 Manuelles Update..."
        cd ~/vinted-bot
        git pull
        sudo systemctl restart vinted-bot
        echo "✅ Update abgeschlossen!"
        ;;
    *)
        echo "Vinted Snipebot - Server Management"
        echo ""
        echo "Benutzung: $0 {start|stop|restart|status|logs|update}"
        echo ""
        echo "  start   - Bot und Updater starten"
        echo "  stop    - Bot und Updater stoppen"
        echo "  restart - Bot und Updater neustarten"
        echo "  status  - Status anzeigen"
        echo "  logs    - Logs anzeigen"
        echo "  update  - Manuelles Update laden"
        ;;
esac
