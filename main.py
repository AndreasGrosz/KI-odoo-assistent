#!/usr/bin/env python3
"""
KI-Kontaktassistent für Odoo - Hauptprogramm
Automatische Erfassung und Pflege von Kontaktdaten aus E-Mails
"""

import imaplib
import email
import re
import time
import os
import hashlib
from datetime import datetime
from email.header import decode_header
from typing import Optional, Tuple
import sys

# Import der anderen Module
from config_manager import ConfigManager
from data_extractor import DataExtractor
from odoo_manager import OdooManager


class KIKontaktAssistent:
    def __init__(self, config_file: str = "config-sys.yml"):
        """Initialisierung des KI-Kontaktassistenten"""

        # Komponenten initialisieren
        self.config_manager = ConfigManager(config_file)
        self.config = self.config_manager.get_config()
        self.logger = self.config_manager.get_logger()

        # Odoo-Verbindung herstellen
        odoo_models, odoo_uid = self.config_manager.get_odoo_connections()

        # Module initialisieren
        self.data_extractor = DataExtractor(self.config, self.logger, self.config_manager.get_prompts())
        self.odoo_manager = OdooManager(self.config, self.logger, odoo_models, odoo_uid, self.config_manager.get_prompts())

        # Verarbeitete E-Mails tracking
        self.processed_emails = self.load_processed_emails()

        self.logger.info("🤖 KI-Kontaktassistent gestartet")
        self.logger.info(f"📊 {len(self.odoo_manager.odoo_categories)} Kategorien verfügbar")

    def load_processed_emails(self) -> set:
        """Lädt bereits verarbeitete E-Mail-IDs (Duplikat-Schutz)"""
        try:
            processed_file = "data/processed_emails.txt"
            os.makedirs(os.path.dirname(processed_file), exist_ok=True)

            if os.path.exists(processed_file):
                with open(processed_file, 'r') as f:
                    return set(line.strip() for line in f if line.strip())
            return set()
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Laden verarbeiteter E-Mails: {e}")
            return set()

    def save_processed_email(self, email_id: str):
        """Speichert verarbeitete E-Mail-ID"""
        try:
            processed_file = "data/processed_emails.txt"
            os.makedirs(os.path.dirname(processed_file), exist_ok=True)

            with open(processed_file, 'a', encoding='utf-8') as f:
                f.write(f"{email_id}\n")
            self.processed_emails.add(email_id)

            # Cleanup alter Einträge (alle 1000 Einträge)
            self.cleanup_processed_emails()

        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Speichern der E-Mail-ID: {e}")

    def cleanup_processed_emails(self):
        """Bereinigt alte verarbeitete E-Mail-IDs"""
        try:
            # Vereinfacht: Behalte nur letzten 1000 Einträge
            if len(self.processed_emails) > 1000:
                self.processed_emails = set(list(self.processed_emails)[-1000:])

                processed_file = "data/processed_emails.txt"
                with open(processed_file, 'w', encoding='utf-8') as f:
                    for email_id in self.processed_emails:
                        f.write(f"{email_id}\n")

        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Cleanup: {e}")

    def extract_forwarder_email(self, email_message) -> Optional[str]:
        """Extrahiert die E-Mail-Adresse des Weiterleiters"""
        try:
            from_header = email_message.get('From', '')
            if from_header:
                decoded_from = self.decode_email_header(from_header)
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', decoded_from)
                if email_match:
                    forwarder_email = email_match.group()
                    if 'ki-adress-admin' not in forwarder_email:
                        return forwarder_email

            # Fallback: Admin-E-Mail
            return self.config.get('assistant', {}).get('admin_email')

        except Exception as e:
            self.logger.error(f"❌ Fehler bei Weiterleiter-E-Mail-Extraktion: {e}")
            return self.config.get('assistant', {}).get('admin_email')

    def extract_primary_email(self, email_message) -> Optional[str]:
        """Extrahiert die ursprüngliche Absender-E-Mail aus weitergeleiteter E-Mail ODER aus manuellem Input"""
        try:
            # E-Mail-Body nach ursprünglicher E-Mail durchsuchen
            body = self.get_email_body_text(email_message)
            if body:
                # Konfigurierbare maximale Länge für bessere Extraktion
                max_email_length = self.config.get('assistant', {}).get('max_email_length', 3000)
                search_body = body[:max_email_length * 2]  # Doppelte Länge für Suche

                self.logger.info(f"🔍 E-Mail-Body für Extraktion (erste 500 Zeichen): {search_body[:500]}...")

                # NEUE: Prüfe ob es sich um manuellen Input handelt (kein E-Mail-Header-Kontext)
                manual_input_indicators = [
                    'von:', 'from:', 'forwarded message', 'weitergeleitete nachricht',
                    'original message', 'subject:', 'betreff:', 'sent:', 'gesendet:'
                ]

                has_email_context = any(indicator in search_body.lower() for indicator in manual_input_indicators)

                if not has_email_context:
                    self.logger.info("📝 Manueller Kontakt-Input erkannt (kein E-Mail-Kontext)")
                    # Suche direkt nach E-Mail-Adressen im Content
                    email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
                    email_matches = re.findall(email_pattern, search_body)

                    for email_addr in email_matches:
                        clean_email = email_addr.strip()
                        # Ausschlüsse: interne E-Mails
                        if (clean_email and
                            'ki-adress-admin' not in clean_email and
                            'ki-kontakt-admin' not in clean_email and
                            '@5gfrei.ch' not in clean_email and
                            '@andreas-gross.ch' not in clean_email):
                            self.logger.info(f"🎯 E-Mail aus manuellem Input gefunden: {clean_email}")
                            return clean_email

                    # Fallback: Keine E-Mail im manuellen Input gefunden
                    self.logger.warning("⚠️ Manueller Input ohne E-Mail-Adresse - verwende Dummy")
                    return "manual-contact@placeholder.local"

                # Normale weitergeleitete E-Mail-Verarbeitung
                # Erweiterte Suche nach "Von:" oder "From:" Zeilen in weitergeleiteten E-Mails
                from_patterns = [
                    # HTML-Patterns für Thunderbird-Weiterleitung
                    r'Von:\s*</th>\s*<td><a[^>]*href="mailto:([^"]+)"',
                    r'From:\s*</th>\s*<td><a[^>]*href="mailto:([^"]+)"',
                    # Text-Patterns
                    r'Von:\s*([^<\n\r\s]+@[^>\n\r\s]+)',
                    r'From:\s*([^<\n\r\s]+@[^>\n\r\s]+)',
                    r'Von:\s*.*?<([^>\n\r]+@[^>\n\r]+)>',
                    r'From:\s*.*?<([^>\n\r]+@[^>\n\r]+)>',
                    # HTML-Pattern ohne <th>
                    r'Von:[^>]*>([^<\s]+@[^<\s]+)<',
                    r'From:[^>]*>([^<\s]+@[^<\s]+)<',
                    # Erweiterte Patterns für deutsche E-Mails
                    r'Absender:\s*([^<\n\r\s]+@[^>\n\r\s]+)',
                    r'E-Mail:\s*([^<\n\r\s]+@[^>\n\r\s]+)',
                    # Pattern für komplexere Signaturen
                    r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
                ]

                found_emails = set()

                for i, pattern in enumerate(from_patterns):
                    matches = re.findall(pattern, search_body, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                    self.logger.debug(f"🔍 Pattern {i+1}: Matches: {matches}")
                    for match in matches:
                        clean_email = match.strip()
                        # Ausschlüsse: interne E-Mails
                        if (clean_email and
                            '@' in clean_email and
                            'ki-adress-admin' not in clean_email and
                            'ki-kontakt-admin' not in clean_email and
                            '@5gfrei.ch' not in clean_email and
                            '@andreas-gross.ch' not in clean_email and
                            len(clean_email) > 5):
                            found_emails.add(clean_email)

                # Priorisiere E-Mails aus der Signatur (häufig am Ende)
                if found_emails:
                    # Sortiere nach Position im Text (E-Mails weiter hinten sind wahrscheinlicher Signaturen)
                    email_positions = []
                    for email_addr in found_emails:
                        position = search_body.rfind(email_addr)
                        email_positions.append((position, email_addr))

                    # Sortiere nach Position (hinten zuerst)
                    email_positions.sort(reverse=True)
                    best_email = email_positions[0][1]

                    self.logger.info(f"🎯 Primäre E-Mail gefunden: {best_email}")
                    return best_email

            self.logger.warning("⚠️ Keine primäre E-Mail-Adresse gefunden")
            return None

        except Exception as e:
            self.logger.error(f"❌ Fehler bei E-Mail-Extraktion: {e}")
            return None

    def decode_email_header(self, header_value: str) -> str:
        """Dekodiert E-Mail-Header"""
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ''

            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += part

            return decoded_string
        except Exception:
            return header_value

    def get_email_body_text(self, email_message) -> str:
        """Extrahiert Klartext aus E-Mail-Body (mit Bild-Entfernung)"""
        try:
            body_text = ""

            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))

                    # Überspringe Anhänge und Bilder
                    if ('attachment' in content_disposition or
                        content_type.startswith('image/') or
                        content_type.startswith('application/') or
                        content_type.startswith('audio/') or
                        content_type.startswith('video/')):
                        self.logger.debug(f"🖼️ Überspringe {content_type}: {content_disposition}")
                        continue

                    # Nur Text-Inhalte verarbeiten
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_text = payload.decode('utf-8', errors='ignore')
                            break  # Nehme ersten text/plain Teil
                    elif content_type == "text/html" and not body_text:
                        # HTML als Fallback wenn kein text/plain vorhanden
                        payload = part.get_payload(decode=True)
                        if payload:
                            html_content = payload.decode('utf-8', errors='ignore')
                            # Einfache HTML-zu-Text Konvertierung
                            body_text = self.html_to_text(html_content)
            else:
                # Nicht-multipart E-Mail
                content_type = email_message.get_content_type()
                if content_type == "text/plain":
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode('utf-8', errors='ignore')
                elif content_type == "text/html":
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        html_content = payload.decode('utf-8', errors='ignore')
                        body_text = self.html_to_text(html_content)

            # Zusätzliche Bereinigung: Entferne Base64-kodierte Bilder und Anhänge
            if body_text:
                # Entferne Base64-Datenblöcke
                body_text = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', '[BILD_ENTFERNT]', body_text)
                # Entferne lange Base64-Strings
                body_text = re.sub(r'[A-Za-z0-9+/]{100,}={0,2}', '[BASE64_ENTFERNT]', body_text)
                # Entferne CID-Referenzen
                body_text = re.sub(r'cid:[A-Za-z0-9@.-]+', '[CID_ENTFERNT]', body_text)
                self.logger.debug(f"📧 E-Mail-Body bereinigt (Länge: {len(body_text)} Zeichen)")

            return body_text

        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim E-Mail-Text extrahieren: {e}")
            return ""

    def html_to_text(self, html_content: str) -> str:
        """Einfache HTML-zu-Text Konvertierung"""
        try:
            # Entferne HTML-Tags
            text = re.sub(r'<[^>]+>', ' ', html_content)
            # Entferne HTML-Entities
            text = text.replace('&nbsp;', ' ')
            text = text.replace('&amp;', '&')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&quot;', '"')
            # Normalisiere Whitespace
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei HTML-zu-Text Konvertierung: {e}")
            return html_content

    def extract_email_content(self, email_message) -> Tuple[str, str]:
        """Extrahiert E-Mail-Inhalt und Biographie mit verbesserter Hashtag-Erkennung"""
        body = self.get_email_body_text(email_message)

        if not body:
            return "", ""

        # Erweiterte maximale Länge aus Konfiguration
        max_bio_length = self.config.get('assistant', {}).get('max_biography_length', 1000)

        # Erste Zeilen als Biographie - aber intelligenter
        lines = [line.strip() for line in body.split('\n') if line.strip()]

        # Suche nach Hashtags und substantiellen Inhalten in den ersten Zeilen
        biography_lines = []
        for i, line in enumerate(lines[:15]):  # Erste 15 Zeilen prüfen (erweitert)
            # Stoppe bei typischen E-Mail-Weiterleitungsmarkern
            if any(marker in line.lower() for marker in [
                '-------- weitergeleitete nachricht',
                'forwarded message',
                'original message',
                'von:', 'from:', 'sent:', 'gesendet:',
                'subject:', 'betreff:', 'date:', 'datum:'
            ]):
                break

            # Sammle substantielle Zeilen für Biographie
            if (len(line) > 10 and
                not line.startswith('>') and
                not line.startswith('--') and
                '@' not in line or '#' in line):  # E-Mail-Adressen vermeiden, außer es sind Hashtags dabei
                biography_lines.append(line)

        # Kombiniere zu Biographie
        biography = ' '.join(biography_lines) if biography_lines else (lines[0] if lines else "")

        # Begrenze Biographie mit konfigurierbarer Länge
        if len(biography) > max_bio_length:
            biography = biography[:max_bio_length] + "..."

        return body, biography

    def generate_email_id(self, email_message) -> str:
        """Generiert eindeutige ID für E-Mail (robuster)"""
        try:
            # Primär: Message-ID verwenden
            message_id = email_message.get('Message-ID')
            if message_id:
                unique_id = hashlib.md5(message_id.encode()).hexdigest()
                self.logger.debug(f"📬 E-Mail-ID von Message-ID: {unique_id}")
                return unique_id

            # Fallback: Hash aus wichtigen Headern
            sender = email_message.get('From', '')
            subject = email_message.get('Subject', '')
            date = email_message.get('Date', '')

            # Zusätzlich ersten Teil des Bodies für bessere Eindeutigkeit
            body = self.get_email_body_text(email_message)
            body_snippet = body[:200] if body else ""

            combined = f"{sender}{subject}{date}{body_snippet}"
            unique_id = hashlib.md5(combined.encode()).hexdigest()
            self.logger.debug(f"📬 E-Mail-ID von Fallback: {unique_id}")
            return unique_id

        except Exception as e:
            # Notfall-Fallback
            self.logger.warning(f"⚠️ Fehler bei E-Mail-ID Generierung: {e}")
            return hashlib.md5(str(time.time()).encode()).hexdigest()

    def process_emails(self):
        """Hauptschleife: Verarbeitet E-Mails"""
        self.logger.info("📧 Starte E-Mail-Verarbeitung...")

        try:
            with imaplib.IMAP4_SSL(self.config['email']['imap_server'], self.config['email']['imap_port']) as mail:
                mail.login(self.config['email']['imap_username'], self.config['email']['imap_password'])
                mail.select('INBOX')

                # Ungelesene E-Mails suchen
                _, message_numbers = mail.search(None, 'UNSEEN')

                if not message_numbers[0]:
                    self.logger.info("📭 Keine neuen E-Mails")
                    return

                email_count = len(message_numbers[0].split())
                self.logger.info(f"📬 {email_count} neue E-Mail(s) gefunden")

                success_count = 0
                error_count = 0

                for i, num in enumerate(message_numbers[0].split(), 1):
                    try:
                        self.logger.info(f"📧 Verarbeite E-Mail {i}/{email_count}")
                        if self.process_single_email(mail, num):
                            success_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        self.logger.error(f"❌ Fehler bei E-Mail {num}: {e}")
                        error_count += 1

                self.logger.info(f"📊 Ergebnis: ✅ {success_count} erfolgreich, ❌ {error_count} Fehler")

        except Exception as e:
            self.logger.error(f"❌ Fehler beim E-Mail-Abruf: {e}")

    def process_single_email(self, mail, email_num) -> bool:
        """Verarbeitet eine einzelne E-Mail (erweitert für manuellen Input)"""
        try:
            # E-Mail abrufen
            _, msg_data = mail.fetch(email_num, '(RFC822)')
            email_message = email.message_from_bytes(msg_data[0][1])

            # Prüfe ob es sich um eine Antwort auf KI-Rückfrage handelt
            subject = email_message.get('Subject', '')
            body = self.get_email_body_text(email_message)

            # Erweiterte Erkennung von KI-Rückfrage-Antworten
            is_ki_response = (
                'Re: KI-Rückfrage' in subject or
                'KI-Rückfrage' in subject or
                'ki-kontakt-admin@andreas-gross.ch' in body or
                ('bei der Verarbeitung der E-Mail' in body and 'konnte ich folgende Kategorien nicht zuordnen' in body)
            )

            if is_ki_response:
                self.logger.info("📧 Antwort auf KI-Rückfrage erkannt - verarbeite Kategorie-Update")

                # Versuche E-Mail aus dem Body zu extrahieren (aus der zitierten Nachricht)
                target_email = None

                # Pattern 1: "bei der Verarbeitung der E-Mail von xxx"
                email_match1 = re.search(r'bei der Verarbeitung der E-Mail\s+(?:von\s+)?([^@\s]+@[^@\s]+)', body)
                if email_match1:
                    potential_email = email_match1.group(1)
                    # Bereinige die E-Mail (entferne "von" falls vorhanden)
                    if potential_email.startswith('von'):
                        target_email = potential_email[3:].strip()
                    else:
                        target_email = potential_email.strip()

                # Pattern 2: Aus Betreff extrahieren (falls vorhanden)
                if not target_email:
                    email_match2 = re.search(r'für\s+([^@\s]+@[^@\s]+)', subject)
                    if email_match2:
                        target_email = email_match2.group(1)

                if target_email:
                    self.logger.info(f"🎯 Ziel-E-Mail identifiziert: {target_email}")

                    # Weiterleiter-E-Mail für Bestätigung extrahieren
                    forwarder_email = self.extract_forwarder_email(email_message)

                    # Extrahiere neue Kategorien aus der Antwort (erste Zeile)
                    first_line = body.split('\n')[0] if body else ""
                    hashtags = re.findall(r'#([a-zA-ZäöüÄÖÜß0-9]+)', first_line)
                    at_tags = re.findall(r'@([a-zA-ZäöüÄÖÜß0-9]+)', first_line)

                    # Kombiniere beide Tag-Typen
                    all_categories = hashtags + at_tags

                    if all_categories:
                        self.logger.info(f"🏷️ Neue Kategorien gefunden: {all_categories} für {target_email}")

                        # Biographie extrahieren: Alles VOR dem ersten Hashtag
                        new_biography = ""
                        for line in body.split('\n'):
                            line = line.strip()
                            # Stoppe beim ersten Hashtag oder @-Tag
                            if line and (line.startswith('#') or line.startswith('@')):
                                break
                            if line:
                                new_biography += line + " "

                        new_biography = new_biography.strip()

                        # Update sowohl Kategorien als auch Biographie
                        success = self.update_contact_categories_and_biography(target_email, all_categories, new_biography)

                        if success:
                            # Optional: Bestätigungs-E-Mail für Kategorie-Update
                            if (self.config.get('assistant', {}).get('send_confirmation_email', False) and
                                forwarder_email):
                                existing_contact = self.odoo_manager.find_existing_contact(target_email)
                                if existing_contact:
                                    contact_data = {
                                        'categories': all_categories,
                                        'biography': new_biography if new_biography else "Keine neue Biographie"
                                    }
                                    self.odoo_manager.send_confirmation_email(
                                        target_email, contact_data, forwarder_email, 'category_updated', existing_contact['id'])

                            mail.store(email_num, '+FLAGS', '\\Seen')
                            return True
                        else:
                            self.logger.warning("⚠️ Kategorie-/Biographie-Update fehlgeschlagen")
                    else:
                        self.logger.warning("⚠️ Keine Kategorien in der Antwort gefunden")
                else:
                    self.logger.warning("⚠️ Konnte Ziel-E-Mail nicht extrahieren")

                # Fallback: Normale Verarbeitung
                self.logger.info("ℹ️ Fallback zu normaler E-Mail-Verarbeitung")

            # Duplikat-Schutz
            email_id = self.generate_email_id(email_message)
            if email_id in self.processed_emails:
                self.logger.info(f"⏭️ E-Mail bereits verarbeitet")
                return True

            # Weiterleiter-E-Mail extrahieren
            forwarder_email = self.extract_forwarder_email(email_message)
            if not forwarder_email:
                self.logger.warning("⚠️ Keine Weiterleiter-E-Mail gefunden")
                return False

            # Ursprüngliche Absender-E-Mail extrahieren (oder aus manuellem Input)
            primary_email = self.extract_primary_email(email_message)
            if not primary_email:
                self.logger.warning("⚠️ Keine Absender-E-Mail gefunden")
                return False

            # NEUE: Manueller Input-Erkennung
            is_manual_input = primary_email == "manual-contact@placeholder.local"

            if is_manual_input:
                self.logger.info("📝 Manueller Kontakt-Input wird verarbeitet")

                # Generiere eine eindeutige E-Mail basierend auf Inhalt
                content_hash = hashlib.md5(body.encode()).hexdigest()[:8]
                primary_email = f"manual-{content_hash}@manual-contact.local"

                self.logger.info(f"📧 Generierte E-Mail für manuellen Kontakt: {primary_email}")

            # E-Mail-Inhalt extrahieren
            email_text, biography = self.extract_email_content(email_message)

            self.logger.info(f"📧 Verarbeite: {primary_email} (von: {forwarder_email}) {'[MANUELL]' if is_manual_input else ''}")

            # KI-Datenextraktion mit spezieller Behandlung für manuellen Input
            if is_manual_input:
                contact_data = self.data_extractor.extract_manual_contact_data(email_text, biography, primary_email)
            else:
                contact_data = self.data_extractor.extract_contact_data(email_text, biography, primary_email)

            if not contact_data:
                self.logger.warning("⚠️ Keine Kontaktdaten extrahiert")
                return False

            # Debug-Info
            self.data_extractor.log_extracted_data(contact_data)

            # Kontakt erstellen/aktualisieren
            success = self.odoo_manager.create_or_update_contact(primary_email, contact_data, forwarder_email)

            if success:
                mail.store(email_num, '+FLAGS', '\\Seen')
                self.save_processed_email(email_id)
                self.logger.info(f"✅ {'Manueller Kontakt' if is_manual_input else 'E-Mail'} erfolgreich verarbeitet")
                return True
            else:
                self.logger.error(f"❌ {'Manueller Kontakt' if is_manual_input else 'E-Mail'}-Verarbeitung fehlgeschlagen")
                return False

        except Exception as e:
            self.logger.error(f"❌ Fehler bei E-Mail-Verarbeitung: {e}")
            return False

    def update_contact_categories_and_biography(self, email: str, new_categories: list, new_biography: str):
        """Aktualisiert Kategorien UND Biographie für existierenden Kontakt"""
        try:
            # Kontakt suchen
            existing_contact = self.odoo_manager.find_existing_contact(email)
            if not existing_contact:
                self.logger.warning(f"⚠️ Kontakt {email} nicht gefunden für Update")
                return False

            # Kategorien validieren
            valid_category_ids, invalid_categories = self.odoo_manager.validate_categories(new_categories)

            if invalid_categories:
                self.logger.warning(f"⚠️ Unbekannte Kategorien werden ignoriert: {invalid_categories}")

            # Update-Daten zusammenstellen
            update_data = {}

            # Kategorien aktualisieren
            if valid_category_ids:
                existing_cat_ids = [cat[0] if isinstance(cat, (list, tuple)) else cat
                                  for cat in existing_contact.get('category_id', [])]
                combined_cat_ids = list(set(existing_cat_ids + valid_category_ids))
                update_data['category_id'] = [(6, 0, combined_cat_ids)]
                self.logger.info(f"🏷️ Kategorien werden erweitert: {new_categories}")

            # Biographie aktualisieren
            if new_biography and new_biography.strip():
                existing_comment = existing_contact.get('comment', '').strip()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                enhanced_biography = f"{new_biography}\n\n[KI-Update {timestamp}]"

                if existing_comment:
                    # Prüfe ob die neue Biographie bereits vorhanden ist
                    if new_biography.strip() not in existing_comment:
                        combined_comment = f"{existing_comment}\n\n{enhanced_biography}"
                        update_data['comment'] = combined_comment
                        self.logger.info(f"📝 Biographie erweitert: {new_biography[:50]}...")
                    else:
                        self.logger.info("📝 Biographie bereits vorhanden - überspringe")
                else:
                    update_data['comment'] = enhanced_biography
                    self.logger.info("📝 Neue Biographie hinzugefügt")

            # Update durchführen wenn Änderungen vorhanden
            if update_data:
                try:
                    result = self.odoo_manager.odoo_models.execute_kw(
                        self.odoo_manager.config['odoo']['database'],
                        self.odoo_manager.odoo_uid,
                        self.odoo_manager.config['odoo']['password'],
                        'res.partner', 'write',
                        [[existing_contact['id']], update_data]
                    )

                    if result:
                        self.logger.info(f"✅ Kontakt erfolgreich aktualisiert für {email}")
                        return True
                    else:
                        self.logger.error(f"❌ Odoo-Update gab False zurück für {email}")
                        return False

                except Exception as odoo_error:
                    self.logger.error(f"❌ Odoo-Fehler beim Update für {email}: {odoo_error}")
                    return False
            else:
                self.logger.info(f"ℹ️ Keine Änderungen nötig für {email}")
                return True

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Kontakt-Update: {e}")
            return False

    def run(self):
        """Startet den KI-Assistenten"""
        self.logger.info("🚀 KI-Kontaktassistent läuft...")

        check_interval = self.config['email']['check_interval']
        self.logger.info(f"⏱️ Check-Intervall: {check_interval} Sekunden")

        try:
            iteration = 0
            while True:
                iteration += 1
                self.logger.info(f"🔄 Iteration {iteration} - {datetime.now().strftime('%H:%M:%S')}")

                # E-Mails verarbeiten
                self.process_emails()

                # Kategorien neu laden (alle 50 Iterationen)
                if iteration % 50 == 0:
                    self.logger.info("🔄 Lade Kategorien neu...")
                    self.odoo_manager.odoo_categories = self.odoo_manager.load_odoo_categories()

                time.sleep(check_interval)

        except KeyboardInterrupt:
            self.logger.info("🛑 KI-Assistent gestoppt (Ctrl+C)")
        except Exception as e:
            self.logger.error(f"❌ Kritischer Fehler: {e}")


if __name__ == "__main__":
    print("🤖 KI-Kontaktassistent für Odoo")
    print("=" * 50)

    try:
        assistant = KIKontaktAssistent()
        assistant.run()
    except Exception as e:
        print(f"❌ Fehler beim Start: {e}")
        sys.exit(1)
