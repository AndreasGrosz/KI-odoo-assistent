# 🤖 KI-Kontaktassistent für Odoo

**Automatische Erfassung und Pflege von Kontaktdaten über E-Mail-Weiterleitung mit OpenAI GPT**

---

## 📋 Überblick

Der KI-Kontaktassistent automatisiert die Kontaktpflege in Odoo durch intelligente E-Mail-Verarbeitung. Einfach E-Mails von neuen Kontakten weiterleiten - der Rest passiert automatisch!

### 🎯 Hauptfunktionen

- **🤖 KI-Datenextraktion**: OpenAI GPT analysiert E-Mails und extrahiert Kontaktdaten
- **📧 E-Mail-Weiterleitung**: Einfacher Workflow über E-Mail-Weiterleitung
- **🏷️ Hashtag-Kategorisierung**: Automatische Zuordnung über #Hashtags
- **🔄 Smart-Updates**: Intelligente Ergänzung bestehender Kontakte
- **📨 Rückfrage-System**: Bei unbekannten Kategorien automatische Nachfrage
- **🌍 Multi-Language**: Erkennt Sprachen (DE/EN/RU) automatisch
- **🏠 Adress-Parsing**: Intelligente Aufteilung von Adressen (CH/DE/AT/RU)

---

## 🚀 Workflow

### 1. E-Mail-Weiterleitung
```
Neue E-Mail von: kunde@example.com
↓
Weiterleitung an: ki-kontakt-admin@andreas-gross.ch
Mit Biographie: "Kundenanfrage Zürich. #Kunde #English"
```

### 2. Automatische Verarbeitung
- ✅ **Kontakt-Check**: Prüfung ob bereits in Odoo vorhanden
- ✅ **KI-Analyse**: GPT extrahiert alle verfügbaren Daten
- ✅ **Kategorie-Mapping**: Hashtags → Odoo-Kategorien
- ✅ **Kontakt-Erstellung**: Neue Anlage oder Update

### 3. Rückfrage bei Problemen
```
❌ Unbekannte Kategorie: #5g
💡 Vorschlag: #5gfrei
📧 Automatische Rückfrage-E-Mail
```

---

## 🛠️ Installation & Setup

### Voraussetzungen
- Python 3.8+
- Odoo-Installation mit XML-RPC Zugang
- OpenAI API-Key
- E-Mail-Konto (IMAP/SMTP)

### Installation
```bash
# Repository klonen
git clone <repository-url>
cd KI-odoo-assistent

# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Konfiguration anpassen
cp config-sys.yml.example config-sys.yml
nano config-sys.yml
```

### Konfiguration (config-sys.yml)
```yaml
# OpenAI API
openai:
  api_key: "sk-..."
  model: "gpt-4"
  max_tokens: 1000
  temperature: 0.3

# Odoo Verbindung
odoo:
  url: "https://your-odoo.com"
  database: "your-db"
  username: "admin"
  password: "password"

# E-Mail Einstellungen
email:
  # IMAP (Empfang)
  imap_server: "imap.example.com"
  imap_port: 993
  imap_username: "ki-kontakt-admin@andreas-gross.ch"
  imap_password: "password"
  
  # SMTP (Versand)
  smtp_server: "smtp.example.com" 
  smtp_port: 465
  smtp_use_ssl: true
  smtp_username: "ki-kontakt-admin@andreas-gross.ch"
  smtp_password: "password"
  
  check_interval: 50  # Sekunden

# Assistent Einstellungen
assistant:
  admin_email: "admin@example.com"
  unknown_category_action: "ask_sender"
  default_categories: ["Neuer-KI-Eintrag"]

# Logging
logging:
  level: "INFO"
  file: "logs/ki-assistent.log"
```

---

## 🎮 Verwendung

### Start des Assistenten
```bash
python main.py
```

### E-Mail-Weiterleitung
```
An: ki-kontakt-admin@andreas-gross.ch
Betreff: Fwd: Kundenanfrage
Inhalt:
Kundenanfrage aus Zürich, möchte Angebot für Standortdatenblatt.
#Kunde #Schweiz

-------- Weitergeleitete Nachricht --------
Von: max.muster@example.com
[Original E-Mail Inhalt...]
```

### Kategorie-Antworten
Bei unbekannten Kategorien:
```
Antwort auf KI-Rückfrage:
#5gfrei
```

---

## 🧠 KI-Extraktion

### Extrahierte Datenfelder
- **👤 Name**: Vor-/Nachname aus Signatur
- **📧 E-Mail**: Primäre + zusätzliche Adressen  
- **📞 Telefon**: Alle Formate (+41, 079, international)
- **🏠 Adresse**: Straße, PLZ, Ort, Land
- **🌐 Website**: URLs aus Signatur
- **🏢 Firma**: Firmenname vs. Personenname
- **💼 Position**: Jobtitel/Funktion
- **🌍 Sprache**: Automatische Erkennung
- **🏷️ Kategorien**: #Hashtags → Odoo-Kategorien

### Intelligente Features
- **📍 Adress-Parsing**: Unterstützt CH/DE/AT/RU Formate
- **🔄 Duplikat-Schutz**: Verhindert mehrfache Verarbeitung
- **📝 Biographie-Verwaltung**: Chronologische Ergänzung
- **⚡ Fallback-Mechanismen**: Robuste Verarbeitung

---

## 📊 Verfügbare Kategorien

```
5Gfrei, Arzt, Auditor, Buchkäufer, Clear und OT, CoS,
EDV, Elektronik-Techniker, english, Ernährung, Familienmitg,
FrScn 1977, FZ, Int Dianetik, Kunde, Lieferant, PC,
Rechtsanwalt, Techniker, Telefonliste, Verkäufer
```

**Verwendung**: `#Kunde #english #Lieferant`

---

## 📁 Projektstruktur

```
KI-odoo-assistent/
├── main.py                 # Hauptprogramm & E-Mail-Verarbeitung
├── config_manager.py       # Konfiguration & API-Setup  
├── data_extractor.py       # OpenAI GPT Integration
├── odoo_manager.py         # Odoo-Operationen & Kategorien
├── config-sys.yml          # Konfigurationsdatei
├── requirements.txt        # Python Dependencies
├── logs/                   # Log-Dateien
├── data/                   # Verarbeitungshistorie
└── README1ST.md           # Diese Dokumentation
```

---

## 🔧 Monitoring & Logs

### Log-Levels
- **INFO**: Normale Verarbeitung
- **WARNING**: Unbekannte Kategorien, kleinere Probleme  
- **ERROR**: Verarbeitungsfehler, API-Probleme
- **DEBUG**: Detaillierte Diagnose-Information

### Typische Log-Ausgaben
```
✅ Neuer Kontakt erstellt: max.muster@example.com (ID: 12345)
⚠️ Unbekannte Kategorien: ['5g'] 
📧 Kategorie-Rückfrage erfolgreich gesendet
🔄 Kategorien neu geladen (alle 50 Iterationen)
```

---

## 🚨 Troubleshooting

### Häufige Probleme

**🔐 Odoo-Authentifizierung fehlgeschlagen**
```
Lösung: Benutzerdaten in config-sys.yml prüfen
```

**📧 SMTP SSL Fehler**  
```
Lösung: smtp_use_ssl: true für Port 465
        smtp_use_tls: true für Port 587
```

**🤖 OpenAI API Fehler**
```
Lösung: API-Key prüfen, Kontingent überprüfen
```

**📧 E-Mail nicht verarbeitet**
```
Lösung: Logs prüfen, E-Mail-Parsing analysieren
```

### Debug-Modus
```yaml
logging:
  level: "DEBUG"  # Aktiviert ausführliche Logs
```

---

## 🔒 Sicherheit & Datenschutz

- **🔐 Verschlüsselte Verbindungen**: TLS/SSL für E-Mail und Odoo
- **🗄️ Lokale Verarbeitung**: Keine Daten-Weiterleitung an Dritte
- **🔑 API-Key Sicherheit**: Sichere Speicherung in Konfiguration
- **📝 DSGVO-Konform**: Automatische Datenminimierung
- **🗃️ Duplikat-Schutz**: Verhindert Mehrfachverarbeitung

---

## 🎯 Performance

- **⚡ Schnell**: ~3-5 Sekunden pro E-Mail
- **💰 Kostengünstig**: Optimierte GPT-Prompts
- **🔄 Zuverlässig**: Robuste Fehlerbehandlung  
- **📈 Skalierbar**: Unterstützt hohe E-Mail-Volumina

---

## 🤝 Support & Wartung

### Automatische Features
- **🔄 Kategorie-Refresh**: Alle 50 Iterationen
- **🧹 Cleanup**: Alte verarbeitete E-Mail-IDs (1000er Grenze)
- **💾 Persistent Storage**: Verarbeitungshistorie in Dateien

### Manueller Support
- **📊 Status-Monitoring**: Über Logs und E-Mail-Benachrichtigungen
- **🛠️ Konfiguration**: Einfache YAML-Anpassungen
- **🔧 Updates**: Modularer Aufbau für einfache Erweiterungen

---

## 🚀 Erweiterte Features

### Geplante Erweiterungen
- **📱 Web-Interface**: Browser-basierte Verwaltung
- **🔔 Slack-Integration**: Benachrichtigungen über Slack
- **📈 Analytics Dashboard**: Verarbeitungsstatistiken
- **🌐 Multi-Tenant**: Mehrere Odoo-Instanzen
- **🔄 Workflow-Engine**: Erweiterte Automatisierung

### Customization
Das modulare Design ermöglicht einfache Anpassungen:
- **data_extractor.py**: GPT-Prompts und Datenvalidierung
- **odoo_manager.py**: Odoo-spezifische Geschäftslogik
- **main.py**: E-Mail-Verarbeitungs-Workflow

---

## 📞 Kontakt & Support

**Entwickler**: Andreas Groß  
**E-Mail**: andreas@5gfrei.ch
**Website**: http://www.Standortdatenblatt.CH

---

*🤖 Automatisierte Kontaktpflege war noch nie so einfach!*
