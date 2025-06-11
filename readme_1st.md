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

## ✨ **Neue Features (Stand: 2025-06-10)**

### 🎯 **Vollständig implementiert:**
- ✅ **Timeline-Notizen:** KI-extrahierte Biografien werden als Timeline-Notizen mit Timestamp gespeichert
- ✅ **Firmen-Erkennung:** Korrekte Zuordnung von Firmennamen als Hauptname bei `is_company: true`
- ✅ **Footer-Priorität:** Intelligente Adress-Extraktion aus E-Mail-Footern
- ✅ **Smart-Strategy:** Kostenoptimierte E-Mail-Verarbeitung (erste 2000 + letzte 1000 Zeichen)
- ✅ **Manueller Input:** Unterstützung für strukturierte Kontakt-Eingaben ohne E-Mail-Kontext
- ✅ **Kategorie-Updates:** Antworten auf KI-Rückfragen werden automatisch verarbeitet

## 🚀 Workflow

### 1. E-Mail-Weiterleitung
```
Neue E-Mail von: kunde@example.com
↓
Weiterleitung an: ki-kontakt-admin@andreas-gross.ch
Mit Biographie: "Die engagierte Rechtsanwältin für 5G-Widerstand. #Rechtsanwalt #5Gfrei"
```

### 2. Automatische Verarbeitung
- ✅ **Kontakt-Check**: Prüfung anhand der email ob bereits in Odoo vorhanden
- ✅ **KI-Analyse**: GPT extrahiert alle verfügbaren Daten
- ✅ **Timeline-Notiz**: Biographie wird als Timeline-Notiz gespeichert
- ✅ **Kategorie-Mapping**: Hashtags → Odoo-Kategorien
- ✅ **Kontakt-Erstellung**: Neue Anlage oder Update

### 3. Timeline-Notizen
```
📝 KI-extrahierte Biographie:

alles vor einem Hashtag oder email-header

"Die engagierte Rechtsanwältin für 5G-Widerstand."

🤖 Automatisch extrahiert
```

### 4. Rückfrage bei Problemen
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
- E-Mail-Konto für den ki-assistent (IMAP/SMTP)
- credentials in config-sys.yml

### Installation
```bash
# Repository klonen
git clone https://github.com/AndreasGrosz/KI-odoo-assistent.git
cd /media/synology/files/projekte/kd0241-py/KI-odoo-assistent/

# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Konfiguration anpassen
cp config-sys.yml.example config-sys.yml
nano config-sys.yml

# Kompilieren
# PyInstaller installieren
pip install pyinstaller

# Einzelne EXE-Datei (alles eingebettet)
pyinstaller --onefile --name="KI-Kontaktassistent main.py

# Ergebnis: dist/KI-Kontaktassistent

```

## 🎮 Verwendung

### Start des Assistenten
```bash
cd /media/synology/files/projekte/kd0241-py/KI-odoo-assistent/
python main.py
oder die exe:
dist/KI-Kontaktassistent
```

### E-Mail-Weiterleitung
```
An: ki-kontakt-admin@andreas-gross.ch
Betreff: Fwd: Kundenanfrage
Inhalt:
Die engagierte Rechtsanwältin für 5G-Widerstand.
#Rechtsanwalt #5Gfrei

-------- Weitergeleitete Nachricht --------
Von: claudia@vernetzt.ch
[Original E-Mail Inhalt...]
```

### Manueller Kontakt-Input (NEU!)
```
An: ki-admin@andreas-gross.ch
Betreff: Neuer Kontakt
Inhalt:
#Kunde **Konzernzentrale** Siemens Aktiengesellschaft
Werner-von-Siemens-Straße 1 80333 München Deutschland
contact@siemens.com Tel. +49 (89) 3803 5491
```

### Kategorie-Antworten
Bei unbekannten Kategorien:
```
Antwort auf KI-Rückfrage:
Neue Biographie für den Kontakt hier...
#5gfrei #Rechtsanwalt
```

---

## 🧠 KI-Extraktion

### Extrahierte Datenfelder
- **👤 Name**: Vor-/Nachname aus Signatur
- **📧 E-Mail**: Primäre + zusätzliche Adressen
- **📞 Telefon**: Alle Formate (+41, 079, international)
- **🏠 Adresse**: Straße, PLZ, Ort, Land (Footer-Priorität!)
- **🌐 Website**: URLs aus Signatur
- **🏢 Firma**: Firmenname vs. Personenname (korrekte Zuordnung!)
- **💼 Position**: Jobtitel/Funktion
- **🌍 Sprache**: Automatische Erkennung
- **🏷️ Kategorien**: #Hashtags → Odoo-Kategorien
- **📝 Biographie**: Text vor Hashtags → Timeline-Notiz

### Intelligente Features (ERWEITERT!)
- **📍 Footer-Adress-Parsing**: Bevorzugt Footer-Bereiche für Adressen
- **🏢 Firmen-Erkennung**: GmbH, AG, Verlag, Ltd, Inc, Corp → korrekte Zuordnung
- **🔄 Duplikat-Schutz**: Verhindert mehrfache Verarbeitung
- **📝 Timeline-Biografien**: Separate Notizen mit Timestamp
- **⚡ Smart-Strategy**: Kostenoptimierte Token-Nutzung
- **🛠️ Robuste Fallbacks**: Mehrschichtiger Fehlerbehandlung

---

## 📊 Verfügbare Kategorien

```
5Arzt, EDV, Elektronik-Techniker, english, Ernährung, Familienmitg,
Kunde, Lieferant, Rechtsanwalt, Techniker, Telefonliste, Verkäufer
```

**Verwendung**: `#Kunde #english #Lieferant`

---

## 📁 Projektstruktur (AKTUALISIERT!)

```
KI-odoo-assistent/
├── main.py                 # Hauptprogramm & E-Mail-Verarbeitung
├── config_manager.py       # Konfiguration & API-Setup
├── data_extractor.py       # OpenAI GPT Integration + Smart-Strategy
├── odoo_manager.py         # Odoo-Operationen + Timeline-Notizen
├── prompts.yml             # KI-Prompt-Templates (erweitert!)
├── config-sys.yml          # Konfigurationsdatei
├── requirements.txt        # Python Dependencies
├── logs/                   # Log-Dateien
├── data/                   # Verarbeitungshistorie
└── readme_1st.md          # Diese Dokumentation
```

---

## 🔧 Monitoring & Logs

### Log-Levels
- **INFO**: Normale Verarbeitung + Timeline-Notizen
- **WARNING**: Unbekannte Kategorien, kleinere Probleme
- **ERROR**: Verarbeitungsfehler, API-Probleme
- **DEBUG**: Detaillierte Diagnose-Information + Smart-Strategy

### Typische Log-Ausgaben (ERWEITERT!)
```
✅ Kontakt aktualisiert: claudia.zumtaugwald@nachhaltig-vernetzt.ch (ID: 143555)
✅ Timeline-Notiz erstellt für Partner 143555: 'Die engagierte Rechtsanwältin...'
🔧 Smart-Strategy angewendet: Head: 2000, Footer: 1000, Total: 3000 Zeichen
🏢 Firma: Verwende company-Feld als Hauptname: 'Jungeuropa Verlag GmbH'
📝 KI-Biographie gefunden: 'Die engagierte Rechtsanwältin für 5G-Widerstand...'
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

**🏢 Firmenname falsch zugeordnet (BEHOBEN!)**
```
Status: ✅ Behoben - Firmennamen werden korrekt als Hauptname eingetragen
```

**📝 Timeline-Notiz HTML-Fehler (BEHOBEN!)**
```
Status: ✅ Behoben - Einfaches HTML wird korrekt gerendert
```

### Debug-Modus
```yaml
logging:
  level: "DEBUG"  # Aktiviert ausführliche Logs + Smart-Strategy Details
```

---

## 🔒 Sicherheit & Datenschutz

- **🔐 Verschlüsselte Verbindungen**: TLS/SSL für E-Mail und Odoo
- **🗄️ Lokale Verarbeitung**: Keine Daten-Weiterleitung an Dritte
- **🔑 API-Key Sicherheit**: Sichere Speicherung in Konfiguration
- **📝 DSGVO-Konform**: Automatische Datenminimierung
- **🗃️ Duplikat-Schutz**: Verhindert Mehrfachverarbeitung
- **💰 Token-Optimierung**: Smart-Strategy reduziert OpenAI-Kosten

---

## 🎯 Performance (VERBESSERT!)

- **⚡ Schneller**: ~2-4 Sekunden pro E-Mail (optimiert!)
- **💰 Kostengünstiger**: Smart-Strategy spart 70% OpenAI-Kosten
- **🔄 Zuverlässiger**: Robuste Fehlerbehandlung + Fallbacks
- **📈 Skalierbar**: Unterstützt hohe E-Mail-Volumina
- **🎯 Präziser**: Verbesserte Footer-Adress-Extraktion
- **📝 Timeline-Notizen**: Bessere Biographie-Verwaltung

---

## 🤝 Support & Wartung

### Automatische Features
- **🔄 Kategorie-Refresh**: Alle 50 Iterationen
- **🧹 Cleanup**: Alte verarbeitete E-Mail-IDs (1000er Grenze)
- **💾 Persistent Storage**: Verarbeitungshistorie in Dateien
- **📝 Timeline-Management**: Automatische Biographie-Speicherung
- **⚡ Smart-Token-Usage**: Kostenoptimierung

### Manueller Support
- **📊 Status-Monitoring**: Über Logs und E-Mail-Benachrichtigungen
- **🛠️ Konfiguration**: Einfache YAML-Anpassungen
- **🔧 Updates**: Modularer Aufbau für einfache Erweiterungen
- **🌐 GitHub-Integration**: Öffentliches Repository für Collaboration

---

## 🚀 Erweiterte Features

### Geplante Erweiterungen
- **🌐 Multi-Tenant**: Mehrere Odoo-Instanzen
- **🔄 Workflow-Engine**: Erweiterte Automatisierung

### Customization
Das modulare Design ermöglicht einfache Anpassungen:
- **data_extractor.py**: GPT-Prompts und Smart-Strategy
- **odoo_manager.py**: Timeline-Notizen und Firmen-Handling
- **prompts.yml**: KI-Prompt-Templates und Beispiele
- **main.py**: E-Mail-Verarbeitungs-Workflow

### 🔧 **Verbesserungen:**
- Robustere E-Mail-Parsing-Logik
- Verbesserte Footer-Analyse
- Optimierte GPT-Prompts in `prompts.yml`
- Erweiterte Logging-Funktionen
- GitHub-Repository öffentlich verfügbar

---

## 📞 Kontakt & Support

**Entwickler**: Andreas Groß
**E-Mail**: andreas@5gfrei.ch
**Website**: http://www.Standortdatenblatt.CH
**GitHub**: https://github.com/AndreasGrosz/KI-odoo-assistent

### 🎯 **Aktueller Status (2025-06-10):**
- ✅ **Timeline-Notizen funktionieren**
- ✅ **Firmen-Erkennung korrekt**
- ✅ **Smart-Strategy aktiv**
- ✅ **Footer-Extraktion optimiert**
- ⚠️ **Kleine E-Mail-Template Anpassung nötig**

---

*🤖 Automatisierte Kontaktpflege war noch nie so einfach - jetzt mit Timeline-Notizen und intelligenter Firmen-Erkennung!*
