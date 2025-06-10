# KI-Kontaktassistent Installation

## 🖥️ **Wo läuft das Script?**

Das Script kann auf verschiedenen Systemen laufen:

### **Option 1: Lokaler PC/Laptop**
- ✅ Einfache Installation
- ✅ Volle Kontrolle
- ❌ PC muss immer laufen

### **Option 2: Server/VPS**
- ✅ 24/7 Betrieb
- ✅ Zuverlässig
- ❌ Mehr technisches Setup

### **Option 3: Raspberry Pi**
- ✅ Günstig, stromsparend
- ✅ 24/7 Betrieb möglich
- ❌ Begrenzte Leistung

## 📋 **Systemvoraussetzungen**

- **Python 3.8+** (empfohlen: Python 3.9+)
- **Internetverbindung** für APIs
- **E-Mail-Zugang** für ki-adressadmin@ingross.de

## 🚀 **Installation Schritt für Schritt**

### **1. Python installieren**
```bash
# Windows: Python von python.org herunterladen
# macOS: 
brew install python3
# Linux:
sudo apt update && sudo apt install python3 python3-pip
```

### **2. Projektordner erstellen**
```bash
mkdir ki-kontakt-assistent
cd ki-kontakt-assistent
```

### **3. Dateien erstellen**
Erstellen Sie folgende Dateien:
- `config-sys.yml` (Konfiguration)
- `ki_kontakt_assistent.py` (Hauptprogramm)
- `requirements.txt` (Dependencies)

### **4. Python-Abhängigkeiten installieren**
```bash
pip install -r requirements.txt
```

### **5. Konfiguration anpassen**
Bearbeiten Sie `config-sys.yml`:

```yaml
# Ihre OpenAI API Daten
openai:
  api_key: "sk-proj-IHR_ECHTER_API_KEY"

# Ihre Odoo Daten
odoo:
  username: "ihre.email@domain.de"
  password: "ihr_odoo_passwort"

# E-Mail-Einstellungen
email:
  imap_server: "mail.ingross.de"      # Anpassen!
  smtp_server: "mail.ingross.de"      # Anpassen!
  imap_username: "ki-adressadmin@ingross.de"
  imap_password: "postfach_passwort"  # Anpassen!
  smtp_username: "ki-adressadmin@ingross.de"
  smtp_password: "postfach_passwort"  # Anpassen!

# Admin-E-Mail für Fehlerberichte
assistant:
  admin_email: "andreas@ingross.de"   # Anpassen!
```

### **6. E-Mail-Postfach einrichten**
1. **Postfach erstellen**: `ki-adressadmin@ingross.de`
2. **IMAP/SMTP aktivieren** in den E-Mail-Einstellungen
3. **Server-Einstellungen prüfen**:
   - IMAP Server: `mail.ingross.de` (oder Ihr Provider)
   - IMAP Port: 993 (SSL)
   - SMTP Server: `mail.ingross.de`
   - SMTP Port: 587 (TLS)

### **7. Test-Lauf**
```bash
python ki_kontakt_assistent.py
```

## 🔧 **Kategorien in Odoo vorbereiten**

Erstellen Sie diese Kategorien in Odoo → Kontakte → Konfiguration → Kontakt-Tags:

- `NeuerKIeintrag` (für alle automatischen Einträge)
- `Kunde`
- `English`
- `Scientology`
- Weitere nach Bedarf...

## 📧 **Workflow testen**

1. **Test-E-Mail senden**:
   - Leiten Sie eine E-Mail an `ki-adressadmin@ingross.de` weiter
   - Fügen Sie in die ersten Zeilen: `"Testkundenprofil aus München #Kunde"`

2. **Logs prüfen**:
   ```bash
   tail -f logs/ki_assistent.log
   ```

3. **Odoo prüfen**:
   - Neuer Kontakt sollte erscheinen
   - Mit Kategorie "NeuerKIeintrag" und "Kunde"

## 🔄 **Automatischer Start**

### **Windows (Task Scheduler)**
1. Task Scheduler öffnen
2. Neue Aufgabe erstellen
3. Programm: `python`
4. Argumente: `C:\Pfad\zu\ki_kontakt_assistent.py`
5. Zeitplan: Bei Systemstart

### **Linux/macOS (systemd/launchd)**
```bash
# systemd Service erstellen
sudo nano /etc/systemd/system/ki-assistent.service

[Unit]
Description=KI Kontakt Assistent
After=network.target

[Service]
Type=simple
User=ihr_benutzer
WorkingDirectory=/pfad/zu/ki-kontakt-assistent
ExecStart=/usr/bin/python3 ki_kontakt_assistent.py
Restart=always

[Install]
WantedBy=multi-user.target

# Service aktivieren
sudo systemctl enable ki-assistent.service
sudo systemctl start ki-assistent.service
```

## 🔍 **Troubleshooting**

### **E-Mail-Verbindung fehlschlägt**
- Server-Einstellungen prüfen
- Firewall/Antivirus prüfen
- 2FA bei E-Mail-Provider deaktivieren (für API-Zugang)

### **Odoo-Verbindung fehlschlägt**
- Login-Daten prüfen
- Internet-Verbindung testen
- Odoo-Status prüfen

### **OpenAI API-Fehler**
- API-Key prüfen
- Guthaben prüfen
- Rate-Limits beachten

### **Kategorien nicht gefunden**
- Kategorien in Odoo erstellen
- Schreibweise prüfen (case-insensitive)
- Logs für Details prüfen

## 📊 **Monitoring**

**Log-Dateien**:
- `logs/ki_assistent.log` - Hauptlog
- Rotation: 10MB, 5 Backup-Dateien

**Status prüfen**:
```bash