#!/usr/bin/env python3
"""
Vinted Snipebot - Auto-Updater
Checks GitHub for updates and restarts the bot if new version is found.
"""

import os
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path

# Configuration
REPO_URL = "https://github.com/MORITZ-P/vinted-snipebot.git"  # ← ÄNDERE ZU DEINEM REPO
LOCAL_REPO_PATH = Path.home() / "vinted-bot"
CHECK_INTERVAL = 300  # 5 Minuten


def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def check_git_installed():
    """Check if git is installed"""
    success, output = run_command("git --version")
    if not success:
        print("❌ Git nicht installiert!")
        print("   Installiere mit: sudo apt install git -y")
        return False
    print(f"✅ Git: {output}")
    return True


def clone_repo():
    """Clone the repository"""
    print(f"📥 Kloniere Repository: {REPO_URL}")

    if LOCAL_REPO_PATH.exists():
        print("   Repository existiert bereits, überspringe...")
        return True

    success, output = run_command(f"git clone {REPO_URL} {LOCAL_REPO_PATH}")
    if success:
        print("✅ Repository geklont!")
        return True
    else:
        print(f"❌ Fehler beim Klonen: {output}")
        return False


def check_for_updates():
    """Check if there are new updates"""
    print(f"🔍 Prüfe auf Updates... ({datetime.now().strftime('%H:%M:%S')})")

    os.chdir(LOCAL_REPO_PATH)

    # Fetch latest changes
    run_command("git fetch origin")

    # Check if local is behind remote
    success, output = run_command("git status -uno")
    if "Your branch is behind" in output or "Your branch is up to date" not in output:
        # Check if there are actually new commits
        success, local_hash = run_command("git rev-parse HEAD")
        success, remote_hash = run_command("git rev-parse origin/main")

        if local_hash != remote_hash:
            print("   🆕 Neue Version gefunden!")
            return True
        else:
            print("   ✅ Bereits aktuell")
            return False

    print("   ✅ Bereits aktuell")
    return False


def pull_updates():
    """Pull the latest updates"""
    print("📥 Lade Updates herunter...")

    os.chdir(LOCAL_REPO_PATH)

    success, output = run_command("git pull origin main")
    if success:
        print("✅ Updates heruntergeladen!")
        return True
    else:
        # Try master branch
        success, output = run_command("git pull origin master")
        if success:
            print("✅ Updates heruntergeladen!")
            return True
        else:
            print(f"❌ Fehler beim Herunterladen: {output}")
            return False


def install_dependencies():
    """Install/update Python dependencies"""
    print("📦 Installiere Dependencies...")

    req_file = LOCAL_REPO_PATH / "requirements.txt"
    if req_file.exists():
        success, output = run_command(f"pip3 install -r {req_file} -q")
        if success:
            print("✅ Dependencies aktuell!")
        else:
            print(f"⚠️  Dependencies Fehler: {output}")


def restart_bot():
    """Restart the bot service"""
    print("🔄 Starte Bot neu...")

    success, output = run_command("sudo systemctl restart vinted-bot")
    if success:
        print("✅ Bot neugestartet!")
        return True
    else:
        # Try direct restart
        run_command("pkill -f vinted_snipebot.py")
        time.sleep(2)
        os.chdir(LOCAL_REPO_PATH)
        run_command("nohup python3 -u vinted_snipebot.py > snipebot.log 2>&1 &")
        print("✅ Bot neugestartet (direkt)!")
        return True


def main():
    """Main update loop"""
    print("=" * 60)
    print("🔄 VINTED SNIPEBOT - AUTO-UPDATER")
    print("=" * 60)
    print(f"📁 Repository: {REPO_URL}")
    print(f"📂 Lokaler Pfad: {LOCAL_REPO_PATH}")
    print(f"⏱️  Check-Intervall: {CHECK_INTERVAL} Sekunden")
    print("=" * 60)

    # Check if git is installed
    if not check_git_installed():
        print("⚠️  Installiere Git mit: sudo apt install git -y")
        return

    # Clone repo if not exists
    if not LOCAL_REPO_PATH.exists():
        if not clone_repo():
            return

    # Install dependencies
    install_dependencies()

    # Main loop
    while True:
        try:
            if check_for_updates():
                if pull_updates():
                    install_dependencies()
                    restart_bot()
                    print("\n✅ Update abgeschlossen!")
                else:
                    print("\n❌ Update fehlgeschlagen!")
            else:
                print(f"   Nächste Prüfung in {CHECK_INTERVAL} Sekunden...")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n🛑 Updater gestoppt!")
            break
        except Exception as e:
            print(f"\n❌ Fehler: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
