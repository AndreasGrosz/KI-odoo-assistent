#!/usr/bin/env python3
"""
Konfigurationsmanagement für KI-Kontaktassistent
Handles Konfiguration, Logging und API-Setup mit Odoo-Status-Erkennung
"""

import yaml
import logging
import openai
import xmlrpc.client
import ssl
import os
import sys
import requests
import re
from datetime import datetime
from pathlib import Path


class ConfigManager:
    def __init__(self, config_file: str = "config-sys.yml"):
        """Initialisiert Konfigurationsmanagement"""
        self.config = self.load_config(config_file)
        self.prompts = self.load_prompts("prompts.yml")
        self.setup_logging()
        self.setup_apis()

        self.logger.info("✅ ConfigManager initialisiert")

    def load_prompts(self, prompts_file: str) -> dict:
        """Lädt die Prompt-Vorlagen aus YAML-Datei"""
        import os

        # Debug-Info
        current_dir = os.getcwd()
        prompts_path = os.path.abspath(prompts_file)
        file_exists = os.path.exists(prompts_file)

        print(f"🔍 DEBUG: Arbeitsverzeichnis: {current_dir}")
        print(f"🔍 DEBUG: Suche prompts.yml in: {prompts_path}")
        print(f"🔍 DEBUG: Datei existiert: {file_exists}")

        if file_exists:
            print(f"🔍 DEBUG: Dateigröße: {os.path.getsize(prompts_file)} Bytes")

        # Liste alle .yml Dateien im Verzeichnis
        yml_files = [f for f in os.listdir('.') if f.endswith('.yml')]
        print(f"🔍 DEBUG: Gefundene .yml Dateien: {yml_files}")

        try:
            with open(prompts_file, 'r', encoding='utf-8') as f:
                prompts = yaml.safe_load(f)

            print(f"✅ {len(prompts)} Prompt-Kategorien geladen")
            return prompts
        except FileNotFoundError:
            print(f"❌ KRITISCHER FEHLER: Prompt-Datei {prompts_file} nicht gefunden!")
            print(f"❌ Vollständiger Pfad: {prompts_path}")
            print(f"❌ System wird beendet - Prompts sind essentiell!")
            import sys
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ YAML-Parsing-Fehler: {e}")
            import sys
            sys.exit(1)

    def load_config(self, config_file: str) -> dict:
        """Lädt die Konfiguration aus YAML-Datei"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Vollständige Validierung der Konfiguration
            self.validate_config(config)

            return config
        except FileNotFoundError:
            print(f"❌ Konfigurationsdatei {config_file} nicht gefunden!")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Fehler beim Laden der Konfiguration: {e}")
            sys.exit(1)

    def validate_config(self, config: dict):
        """Validiert die Konfiguration auf Vollständigkeit"""
        errors = []
        warnings = []

        # Pflichtfelder definieren
        required_sections = {
            'openai': ['api_key', 'model'],
            'odoo': ['url', 'database', 'username', 'password'],
            'email': ['imap_server', 'imap_username', 'imap_password', 'smtp_server', 'smtp_username', 'smtp_password'],
            'assistant': ['admin_email'],
            'logging': ['level', 'file']
        }

        # Prüfe Hauptsektionen
        for section in required_sections.keys():
            if section not in config:
                errors.append(f"Fehlende Sektion: {section}")
                continue

            # Prüfe Pflichtfelder in Sektion
            for field in required_sections[section]:
                if field not in config[section]:
                    errors.append(f"Fehlendes Feld: {section}.{field}")
                elif not config[section][field]:
                    errors.append(f"Leeres Feld: {section}.{field}")

        # Spezielle Validierungen
        if 'openai' in config and 'api_key' in config['openai']:
            api_key = config['openai']['api_key']
            if 'YOUR_' in api_key.upper() or 'HIER_' in api_key.upper():
                errors.append("OpenAI API Key nicht konfiguriert (enthält Platzhalter)")

        if 'odoo' in config and 'username' in config['odoo']:
            username = config['odoo']['username']
            if 'IHR_' in username.upper() or '@DOMAIN' in username.upper():
                errors.append("Odoo Username nicht konfiguriert (enthält Platzhalter)")

        if 'email' in config:
            email_config = config['email']
            for field in ['imap_username', 'smtp_username']:
                if field in email_config and 'ki-adress-admin@ingross.de' not in email_config[field]:
                    warnings.append(f"E-Mail-Feld {field} sollte ki-adress-admin@ingross.de enthalten")

        if 'assistant' in config and 'admin_email' in config['assistant']:
            admin_email = config['assistant']['admin_email']
            if '@' not in admin_email or 'DOMAIN' in admin_email.upper():
                errors.append("Admin E-Mail ungültig oder nicht konfiguriert")

        # Ausgabe der Ergebnisse - OHNE self.logger (da Logger noch nicht existiert)
        if errors:
            print("❌ KONFIGURATIONSFEHLER:")
            for error in errors:
                print(f"   • {error}")
            print("\nBitte korrigieren Sie diese Fehler in config-sys.yml")
            sys.exit(1)

        if warnings:
            print("⚠️ KONFIGURATIONSWARNUNGEN:")
            for warning in warnings:
                print(f"   • {warning}")
            print()

        print("✅ Konfiguration vollständig validiert")

    def setup_logging(self):
        """Richtet das Logging ein"""
        log_config = self.config['logging']
        log_dir = os.path.dirname(log_config['file'])
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # Erweiterte Logging-Konfiguration
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_config['file'], encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Startup-Info loggen
        self.logger.info("=" * 60)
        self.logger.info("🚀 KI-Kontaktassistent Startup")
        self.logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 60)

    def check_odoo_status(self, odoo_url: str) -> dict:
        """Prüft Odoo-Status und erkennt Wartungsfenster"""
        try:
            # 1. Basis-URL prüfen
            base_url = odoo_url.replace('/web', '').rstrip('/')

            self.logger.info(f"🔍 Prüfe Odoo-Status: {base_url}")

            # 2. HTTP-Request mit Timeout
            response = requests.get(base_url, timeout=10, allow_redirects=True)

            # 3. Analysiere Response
            status_info = {
                'available': response.status_code == 200,
                'status_code': response.status_code,
                'maintenance': False,
                'message': '',
                'response_time': response.elapsed.total_seconds()
            }

            # 4. Wartungsmodus-Erkennung
            if response.status_code in [502, 503, 504]:
                status_info['maintenance'] = True
                status_info['message'] = "Server temporär nicht verfügbar (möglicherweise Wartung)"

            # 5. Content-Analyse für Wartungsseiten
            if response.text and len(response.text) > 0:
                content_lower = response.text.lower()
                maintenance_indicators = [
                    'maintenance', 'wartung', 'upgrade', 'scheduled downtime',
                    'temporarily unavailable', 'service unavailable',
                    'under maintenance', 'system upgrade'
                ]

                for indicator in maintenance_indicators:
                    if indicator in content_lower:
                        status_info['maintenance'] = True
                        status_info['message'] = f"Wartungsmodus erkannt: {indicator}"
                        break

            # 6. Zeitfenster-Extraktion (falls in HTML enthalten)
            if status_info['maintenance'] and response.text:
                time_pattern = r'(\d{1,2}:\d{2}[-–]\d{1,2}:\d{2})'
                time_match = re.search(time_pattern, response.text)
                if time_match:
                    status_info['maintenance_window'] = time_match.group(1)
                    status_info['message'] += f" (Zeitfenster: {time_match.group(1)})"

            return status_info

        except requests.exceptions.Timeout:
            return {
                'available': False,
                'status_code': 0,
                'maintenance': True,
                'message': 'Timeout - Server nicht erreichbar (möglicherweise Wartung)',
                'response_time': 10.0
            }
        except requests.exceptions.ConnectionError:
            return {
                'available': False,
                'status_code': 0,
                'maintenance': True,
                'message': 'Verbindungsfehler - Server nicht erreichbar',
                'response_time': 0
            }
        except Exception as e:
            return {
                'available': False,
                'status_code': 0,
                'maintenance': False,
                'message': f'Unbekannter Fehler: {str(e)}',
                'response_time': 0
            }

    def check_odoo_twitter_status(self) -> str:
        """Prüft Odoo Twitter-Status für aktuelle Meldungen"""
        try:
            # Fallback: Prüfe allgemeine Odoo-Status-Seiten
            status_urls = [
                'https://status.odoo.com',
                'https://www.odoo.com',
            ]

            for url in status_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if 'maintenance' in response.text.lower() or 'downtime' in response.text.lower():
                        return "🔧 Wartungsarbeiten auf Odoo-Status-Seite erkannt"
                except:
                    continue

            return ""
        except:
            return ""

    def setup_apis(self):
        """Richtet die API-Verbindungen ein mit intelligenter Fehlerbehandlung"""
        try:
            # OpenAI
            openai.api_key = self.config['openai']['api_key']
            if not self.config['openai']['api_key'] or 'YOUR_' in self.config['openai']['api_key'].upper():
                raise ValueError("OpenAI API Key nicht konfiguriert!")

            # Odoo
            odoo_config = self.config['odoo']

            self.logger.info(f"🔍 Odoo-Verbindungstest:")
            self.logger.info(f"   URL: {odoo_config['url']}")
            self.logger.info(f"   Database: {odoo_config['database']}")
            self.logger.info(f"   Username: {odoo_config['username']}")

            # Normale Verbindung versuchen
            context = ssl.create_default_context()
            self.odoo_common = xmlrpc.client.ServerProxy(
                f'{odoo_config["url"]}/xmlrpc/2/common', context=context)

            # Server-Erreichbarkeit testen
            try:
                version = self.odoo_common.version()
                self.logger.info(f"✅ Odoo-Server erreichbar: {version}")
            except Exception as e:
                self.logger.error(f"❌ Odoo-Server nicht erreichbar: {e}")

                # ERWEITERTE Fehleranalyse für Server-Down-Erkennung
                error_str = str(e).lower()

                if any(indicator in error_str for indicator in ["timed out", "timeout", "read timeout"]):
                    self.logger.error("🚨 SERVER-PROBLEM ERKANNT: Timeout")
                    self.check_and_report_server_issues(odoo_config['url'], "Timeout")
                elif any(indicator in error_str for indicator in ["connection refused", "connection reset", "connection aborted"]):
                    self.logger.error("🚨 SERVER-PROBLEM ERKANNT: Verbindung verweigert")
                    self.check_and_report_server_issues(odoo_config['url'], "Connection Refused")
                elif any(indicator in error_str for indicator in ["bad gateway", "502", "service unavailable", "503", "gateway timeout", "504"]):
                    self.logger.error("🚨 SERVER-PROBLEM ERKANNT: Gateway-Fehler")
                    self.check_and_report_server_issues(odoo_config['url'], "Gateway Error")
                elif "ssl" in error_str:
                    self.logger.error("💡 Mögliche Ursache: SSL/TLS-Verbindungsproblem")
                else:
                    # Unbekannter Fehler - prüfe trotzdem Status
                    self.check_and_report_server_issues(odoo_config['url'], f"Unbekannter Fehler: {e}")

                raise

            self.odoo_models = xmlrpc.client.ServerProxy(
                f'{odoo_config["url"]}/xmlrpc/2/object', context=context)

            # Odoo Authentifizierung mit Server-Down-Erkennung
            self.logger.info("🔐 Versuche Authentifizierung...")

            try:
                self.odoo_uid = self.odoo_common.authenticate(
                    odoo_config['database'],
                    odoo_config['username'],
                    odoo_config['password'],
                    {}
                )
            except Exception as auth_e:
                # Prüfe ob es ein Server-Problem ist
                auth_error_str = str(auth_e).lower()
                if any(indicator in auth_error_str for indicator in ["timed out", "timeout", "connection", "502", "503", "504", "bad gateway"]):
                    self.logger.error("🚨 SERVER-PROBLEM bei Authentifizierung erkannt!")
                    self.check_and_report_server_issues(odoo_config['url'], f"Auth-Fehler: {auth_e}")
                    raise
                else:
                    # Normaler Auth-Fehler, weiterleiten
                    raise

            if not self.odoo_uid:
                # Hier könnten wir auch nochmal prüfen ob es ein Server-Problem ist
                # indem wir eine einfache Version-Abfrage machen
                try:
                    test_version = self.odoo_common.version()
                    # Server funktioniert, also echter Auth-Fehler
                    error_msg = "❌ Odoo-Authentifizierung fehlgeschlagen!\n"
                    error_msg += "💡 Mögliche Ursachen:\n"
                    error_msg += "   • Falsches Passwort\n"
                    error_msg += "   • 2FA aktiviert → API-Schlüssel benötigt\n"
                    error_msg += "   • Account gesperrt nach zu vielen Versuchen\n"
                    error_msg += "   • Benutzer hat keine API-Berechtigung\n"
                    error_msg += "   • Database-Name falsch\n"
                    error_msg += "\n🔧 Lösungsschritte:\n"
                    error_msg += "   1. Login im Browser testen\n"
                    error_msg += "   2. Bei 2FA: API-Schlüssel erstellen\n"
                    error_msg += "   3. Passwort zurücksetzen\n"
                    error_msg += "   4. Admin kontaktieren\n"

                    raise ValueError(error_msg)
                except:
                    # Server-Problem auch hier
                    self.logger.error("🚨 SERVER-PROBLEM: Authentifizierung gibt False zurück aber Server antwortet nicht")
                    self.check_and_report_server_issues(odoo_config['url'], "Auth returns False + Server unresponsive")
                    raise ValueError("Server-Problem während Authentifizierung")

            self.logger.info("✅ APIs erfolgreich verbunden")
            self.logger.info(f"🔐 Odoo User ID: {self.odoo_uid}")

        except Exception as e:
            self.logger.error(f"❌ API-Setup fehlgeschlagen: {e}")
            sys.exit(1)

    def check_and_report_server_issues(self, odoo_url: str, error_type: str):
        """Prüft und meldet Server-Probleme mit detaillierter Analyse"""
        try:
            self.logger.info("🔍 Führe erweiterte Server-Diagnose durch...")

            # 1. HTTP-Status prüfen
            status = self.check_odoo_status(odoo_url)

            # 2. Twitter-Status prüfen
            twitter_status = self.check_odoo_twitter_status()

            # 3. Detaillierte Fehlermeldung erstellen
            error_msg = f"\n🚨 ODOO-SERVER-PROBLEM ERKANNT!\n"
            error_msg += f"   Fehler-Typ: {error_type}\n"
            error_msg += f"   HTTP-Status: {status.get('status_code', 'N/A')}\n"
            error_msg += f"   Response-Zeit: {status.get('response_time', 0):.2f}s\n"

            if status['maintenance'] or twitter_status:
                error_msg += f"\n💡 BESTÄTIGTE URSACHE: WARTUNGSARBEITEN\n"
                if 'maintenance_window' in status:
                    error_msg += f"   Wartungsfenster: {status['maintenance_window']}\n"
                if twitter_status:
                    error_msg += f"   Status-Update: {twitter_status}\n"
            else:
                error_msg += f"\n💡 MÖGLICHE URSACHEN:\n"
                error_msg += f"   • Geplante Wartungsarbeiten (nicht öffentlich angekündigt)\n"
                error_msg += f"   • Server-Überlastung oder temporäre Ausfälle\n"
                error_msg += f"   • Netzwerk-Probleme\n"

            error_msg += f"\n🔧 LÖSUNGSSCHRITTE:\n"
            error_msg += f"   1. Status prüfen: https://status.odoo.com\n"
            error_msg += f"   2. Twitter prüfen: @OdooStatus\n"
            error_msg += f"   3. 5-15 Minuten warten und neu versuchen\n"
            error_msg += f"   4. Browser-Test: {odoo_url}\n"
            error_msg += f"   5. Bei längerem Ausfall: Odoo-Support kontaktieren\n"

            self.logger.error(error_msg)

        except Exception as diag_e:
            self.logger.warning(f"⚠️ Diagnose fehlgeschlagen: {diag_e}")
            self.logger.error(f"💡 ALLGEMEINE EMPFEHLUNG bei '{error_type}':")
            self.logger.error(f"   • Odoo-Status prüfen: https://status.odoo.com")
            self.logger.error(f"   • Twitter: @OdooStatus")
            self.logger.error(f"   • Kurz warten und neu versuchen")

    def get_config(self) -> dict:
        """Gibt Konfiguration zurück"""
        return self.config

    def get_logger(self) -> logging.Logger:
        """Gibt Logger zurück"""
        return self.logger

    def get_prompts(self) -> dict:
        """Gibt Prompt-Vorlagen zurück"""
        return self.prompts

    def get_odoo_connections(self) -> tuple:
        """Gibt Odoo-Verbindungen zurück"""
        return self.odoo_models, self.odoo_uid
