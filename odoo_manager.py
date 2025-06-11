#!/usr/bin/env python3
"""
Odoo-Integration für Kontaktverwaltung
Handles Odoo-Operationen, Kategorien und Kontakt-CRUD mit YAML-Templates
FIXED VERSION: Korrekte Firmen-Namen-Zuordnung + Timeline-Notizen
"""

import logging
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Tuple


class OdooManager:
    def __init__(self, config: dict, logger: logging.Logger, odoo_models, odoo_uid, prompts: dict):
        """Initialisiert Odoo-Manager"""
        self.config = config
        self.logger = logger
        self.odoo_models = odoo_models
        self.odoo_uid = odoo_uid
        self.prompts = prompts
        self.odoo_categories = self.load_odoo_categories()

    def load_odoo_categories(self) -> Dict[str, int]:
        """Lädt alle verfügbaren Kategorien aus Odoo"""
        try:
            categories = self.odoo_models.execute_kw(
                self.config['odoo']['database'],
                self.odoo_uid,
                self.config['odoo']['password'],
                'res.partner.category', 'search_read', [[]],
                {'fields': ['name']}
            )

            # Case-insensitive Mapping erstellen
            category_map = {}
            for cat in categories:
                original_name = cat['name']
                normalized_name = original_name.lower().strip()
                category_map[normalized_name] = cat['id']

                # Zusätzliche Varianten für bessere Erkennung
                variant1 = normalized_name.replace('-', '')
                variant2 = normalized_name.replace('-', ' ')
                if variant1 != normalized_name:
                    category_map[variant1] = cat['id']
                if variant2 != normalized_name:
                    category_map[variant2] = cat['id']

            self.logger.info(f"📋 {len(categories)} Kategorien aus Odoo geladen")
            if categories:
                sample_cats = list(category_map.keys())[:5]
                self.logger.info(f"📝 Beispiel-Kategorien: {', '.join(sample_cats)}")

            return category_map

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Kategorien: {e}")
            return {}

    def validate_categories(self, categories: List[str]) -> Tuple[List[int], List[str]]:
        """Validiert Kategorien gegen Odoo-Kategorien"""
        valid_category_ids = []
        invalid_categories = []

        for category in categories:
            category_variants = [
                category.lower().strip('#').strip(),
                category.lower().replace('-', ''),
                category.lower().replace('-', ' '),
                category.lower().replace('_', ''),
                category.lower().replace('_', ' ')
            ]

            found = False
            for variant in category_variants:
                if variant in self.odoo_categories:
                    cat_id = self.odoo_categories[variant]
                    if cat_id not in valid_category_ids:
                        valid_category_ids.append(cat_id)
                    found = True
                    break

            if not found:
                invalid_categories.append(category)

        # Standard-Kategorie "Neuer-KI-Eintrag" hinzufügen
        default_cats = self.config['assistant']['default_categories']
        for default_cat in default_cats:
            default_normalized = default_cat.lower()
            if default_normalized in self.odoo_categories:
                cat_id = self.odoo_categories[default_normalized]
                if cat_id not in valid_category_ids:
                    valid_category_ids.append(cat_id)

        return valid_category_ids, invalid_categories

    def find_existing_contact(self, email: str) -> Optional[Dict]:
        """Sucht nach existierendem Kontakt anhand der E-Mail-Adresse"""
        try:
            if not email or not isinstance(email, str) or '@' not in email:
                return None

            search_domain = [['email', '=', email.strip()]]

            contact_ids = self.odoo_models.execute_kw(
                self.config['odoo']['database'],
                self.odoo_uid,
                self.config['odoo']['password'],
                'res.partner', 'search',
                [search_domain]
            )

            if contact_ids:
                contact = self.odoo_models.execute_kw(
                    self.config['odoo']['database'],
                    self.odoo_uid,
                    self.config['odoo']['password'],
                    'res.partner', 'read',
                    [contact_ids[0]],
                    {'fields': ['name', 'email', 'phone', 'street', 'website', 'comment', 'category_id']}
                )[0]

                self.logger.info(f"🔍 Existierender Kontakt gefunden: {email}")
                return contact

            self.logger.info(f"🆕 Kein existierender Kontakt für: {email}")
            return None

        except Exception as e:
            self.logger.warning(f"⚠️ Kontaktsuche übersprungen wegen Odoo-Fehler: {e}")
            return None

    def create_timeline_note(self, partner_id: int, biography: str, contact_data: Dict):
        """Erstellt Timeline-Notiz mit Timestamp für KI-extrahierte Biographie"""
        try:
            if not biography or not biography.strip():
                self.logger.info("📝 Keine Biographie - überspringe Timeline-Notiz")
                return True

            confidence = contact_data.get('confidence', 'medium')
            contact_name = contact_data.get('full_name', 'Kontakt')

            # Timeline-Notiz mit formatiertem HTML erstellen
            # REINER TEXT (garantiert funktioniert):
            note_body = f""" "{biography}" """

            # Timeline-Notiz via message_post erstellen
            self.odoo_models.execute_kw(
                self.config['odoo']['database'],
                self.odoo_uid,
                self.config['odoo']['password'],
                'res.partner', 'message_post',
                [partner_id],
                {
                    'body': note_body,
                    'message_type': 'comment',
                    'subtype_xmlid': 'mail.mt_note',
                    'subject': f'📝 KI-Biographie: {contact_name}'
                }
            )

            self.logger.info(f"✅ Timeline-Notiz erstellt für Partner {partner_id}: '{biography[:50]}...'")
            return True

        except Exception as e:
            self.logger.error(f"❌ Fehler bei Timeline-Notiz-Erstellung: {e}")
            return False

    def create_or_update_contact(self, primary_email: str, contact_data: Dict, forwarder_email: str) -> bool:
        """Erstellt neuen Kontakt oder aktualisiert existierenden (mit Timeline-Notizen)"""
        try:
            existing_contact = self.find_existing_contact(primary_email)

            # Kategorien validieren
            categories = contact_data.get('categories', [])
            valid_category_ids, invalid_categories = self.validate_categories(categories)

            if invalid_categories:
                self.logger.warning(f"⚠️ Unbekannte Kategorien: {invalid_categories}")
                action = self.config.get('assistant', {}).get('unknown_category_action', 'ask_sender')

                if action == 'ask_sender':
                    self.send_category_error_email(primary_email, invalid_categories, contact_data, forwarder_email)

            # Kontaktdaten zusammenführen
            contact_values, biography_for_timeline = self.build_contact_values(contact_data, primary_email, valid_category_ids, existing_contact)

            if existing_contact:
                # Kontakt aktualisieren
                update_values = self.get_update_values(existing_contact, contact_values)
                if update_values:
                    self.odoo_models.execute_kw(
                        self.config['odoo']['database'],
                        self.odoo_uid,
                        self.config['odoo']['password'],
                        'res.partner', 'write',
                        [[existing_contact['id']], update_values]
                    )
                    self.logger.info(f"✅ Kontakt aktualisiert: {primary_email} (ID: {existing_contact['id']})")
                    action = 'updated'
                    contact_id = existing_contact['id']
                else:
                    self.logger.info(f"ℹ️ Kontakt bereits vollständig: {primary_email}")
                    action = 'unchanged'
                    contact_id = existing_contact['id']
            else:
                # Neuen Kontakt erstellen
                contact_id = self.odoo_models.execute_kw(
                    self.config['odoo']['database'],
                    self.odoo_uid,
                    self.config['odoo']['password'],
                    'res.partner', 'create',
                    [contact_values]
                )
                self.logger.info(f"✅ Neuer Kontakt erstellt: {primary_email} (ID: {contact_id})")
                action = 'created'

            # NEUE: Timeline-Notiz für Biographie erstellen (falls vorhanden)
            if biography_for_timeline and biography_for_timeline.strip():
                self.create_timeline_note(contact_id, biography_for_timeline, contact_data)

            # Optional: Bestätigungs-E-Mail senden
            if (self.config.get('assistant', {}).get('send_confirmation_email', False) and
                action in ['created', 'updated']):
                self.send_confirmation_email(primary_email, contact_data, forwarder_email, action, contact_id)

            return True

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Speichern des Kontakts: {e}")
            return False

    def send_category_error_email(self, contact_email: str, invalid_categories: List[str], contact_data: Dict, forwarder_email: str):
        """Sendet Rückfrage bei unbekannten Kategorien an den Weiterleiter (mit YAML-Templates)"""
        try:
            self.logger.info(f"📧 Sende Kategorie-Rückfrage für: {contact_email}")

            # Template aus YAML laden
            category_template = self.prompts.get('category_inquiry', {})
            subject_template = category_template.get('subject_template', 'KI-Rückfrage: Unbekannte Kategorien für {contact_email}')
            body_template = category_template.get('body_template', 'Standard-Rückfrage für {contact_email}')

            msg = MIMEMultipart()
            msg['From'] = self.config['email']['smtp_username']
            msg['To'] = forwarder_email
            msg['Subject'] = subject_template.format(contact_email=contact_email)

            # Ähnliche Kategorien finden
            similar_suggestions = []
            available_cats = sorted(self.odoo_categories.keys())

            for invalid_cat in invalid_categories:
                similar = []
                invalid_lower = invalid_cat.lower()

                for cat in available_cats:
                    cat_lower = cat.lower()
                    if invalid_lower in cat_lower or cat_lower in invalid_lower:
                        similar.append(cat)
                    elif (abs(len(invalid_lower) - len(cat_lower)) <= 2 and
                          len(invalid_lower) > 0 and len(cat_lower) > 0 and
                          invalid_lower[0] == cat_lower[0]):
                        similar.append(cat)

                if similar:
                    similar_suggestions.append(f"'{invalid_cat}' → Vorschlag: {', '.join(similar[:3])}")
                else:
                    similar_suggestions.append(f"'{invalid_cat}' → Keine ähnlichen Kategorien gefunden")

            # Bevorzugte Kategorien aus Konfiguration
            preferred_categories = self.config.get('assistant', {}).get('preferred_categories', [])
            if not preferred_categories:
                preferred_categories = ["Kunde", "Lieferant", "Techniker", "Arzt", "EDV", "english"]

            # Template-Daten zusammenstellen
            template_data = {
                'contact_email': contact_email,
                'invalid_categories': ', '.join(invalid_categories),
                'similar_suggestions': '\n'.join(similar_suggestions),
                'contact_name': contact_data.get('full_name', 'N/A'),
                'contact_company': contact_data.get('company', 'N/A'),
                'contact_phones': ', '.join(contact_data.get('phones', ['N/A'])),
                'preferred_categories': '\n'.join([f"• {cat}" for cat in preferred_categories])
            }

            # Body aus Template erstellen
            body = body_template.format(**template_data)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # E-Mail senden
            self._send_email(msg)
            self.logger.info(f"✅ Kategorie-Rückfrage erfolgreich gesendet an: {forwarder_email}")

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Senden der Rückfrage: {e}")
            self.logger.info("ℹ️ Setze Verarbeitung ohne E-Mail-Versand fort")

    def _send_email(self, msg):
        """Zentrale E-Mail-Versand-Methode"""
        smtp_config = self.config['email']

        if smtp_config.get('smtp_use_ssl', False):
            server = smtplib.SMTP_SSL(smtp_config['smtp_server'], smtp_config['smtp_port'])
        else:
            server = smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port'])
            server.settimeout(10)

            if smtp_config.get('smtp_use_tls', False):
                server.starttls()

        try:
            server.login(smtp_config['smtp_username'], smtp_config['smtp_password'])
            server.send_message(msg)
            server.quit()
        except Exception as e:
            self.logger.error(f"❌ SMTP-Login/Send Fehler: {e}")
            server.quit()
            raise

    def send_confirmation_email(self, contact_email: str, contact_data: Dict, forwarder_email: str,
                              action: str, contact_id: int):
        """Sendet Bestätigungs-E-Mail nach Kontakt-Verarbeitung (mit YAML-Templates)"""
        try:
            self.logger.info(f"📧 Sende Bestätigungs-E-Mail für: {contact_email}")

            # Aktuellen Kontakt aus Odoo laden
            current_contact = self.odoo_models.execute_kw(
                self.config['odoo']['database'],
                self.odoo_uid,
                self.config['odoo']['password'],
                'res.partner', 'read',
                [contact_id],
                {'fields': ['name', 'email', 'phone', 'street', 'city', 'zip', 'country_id',
                           'website', 'function', 'category_id', 'is_company', 'comment']}
            )[0]

            # Kategorien-Namen laden
            category_names = []
            if current_contact.get('category_id'):
                cat_ids = [cat[0] if isinstance(cat, list) else cat for cat in current_contact['category_id']]
                categories = self.odoo_models.execute_kw(
                    self.config['odoo']['database'],
                    self.odoo_uid,
                    self.config['odoo']['password'],
                    'res.partner.category', 'read',
                    [cat_ids],
                    {'fields': ['name']}
                )
                category_names = [cat['name'] for cat in categories]

            # Template aus YAML laden oder Fallback verwenden
            template_key = f'confirmation_{action}' if action in ['created', 'updated'] else 'confirmation_created'
            confirmation_template = self.prompts.get(template_key, {})

            # Fallback-Template falls YAML nicht verfügbar
            if not confirmation_template:
                subject_template = '✅ Kontakt {action}: {contact_email}'
                body_template = '''Hallo,

der Kontakt {contact_email} wurde erfolgreich {action}.

🎯 VOLLSTÄNDIGE KONTAKTDATEN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Name: {contact_name}
🏢 Typ: {contact_type}
📧 E-Mail: {contact_email}
📞 Telefon: {contact_phones}
🏠 Adresse: {contact_address}
🌐 Website: {contact_website}
💼 Position: {contact_position}
🌍 Sprache: {contact_language}
🏷️ Kategorien: {contact_categories}

📝 TIMELINE-NOTIZEN:
Die KI-extrahierte Biographie wurde als Timeline-Notiz hinterlegt und ist im Odoo-Chatter sichtbar.

❓ FEHLENDE DATEN:
{missing_data}

🔗 Odoo-Direktlink: {odoo_link}

💡 HINWEIS: Fehlende Daten können in Odoo nachgetragen oder per E-Mail-Antwort ergänzt werden.

Viele Grüße,
Ihr KI-Assistent'''
            else:
                subject_template = confirmation_template.get('subject_template', '✅ Kontakt {action}: {contact_email}')
                body_template = confirmation_template.get('body_template', 'Kontakt {contact_email} wurde {action}.')

            msg = MIMEMultipart()
            msg['From'] = self.config['email']['smtp_username']
            msg['To'] = forwarder_email

            # Adresse formatieren
            address_parts = []
            if current_contact.get('street'):
                address_parts.append(current_contact['street'])
            if current_contact.get('city') or current_contact.get('zip'):
                city_zip = f"{current_contact.get('zip', '')} {current_contact.get('city', '')}".strip()
                if city_zip:
                    address_parts.append(city_zip)
            if current_contact.get('country_id'):
                country_name = current_contact['country_id'][1] if isinstance(current_contact['country_id'], list) else ""
                if country_name:
                    address_parts.append(country_name)

            address_str = ", ".join(address_parts) if address_parts else "Keine Adresse"

            # Action-Text definieren
            action_text = "erstellt" if action == "created" else "aktualisiert"

            # Fehlende Daten identifizieren
            missing_data = []
            if not current_contact.get('phone'):
                missing_data.append("📞 Telefonnummer")
            if not current_contact.get('street'):
                missing_data.append("🏠 Adresse")
            if not current_contact.get('website'):
                missing_data.append("🌐 Website")
            if not current_contact.get('function'):
                missing_data.append("💼 Position/Funktion")
            if not category_names:
                missing_data.append("🏷️ Kategorien")

            missing_text = '\n'.join(missing_data) if missing_data else "✅ Alle wichtigen Daten erfasst!"

            # Template-Daten zusammenstellen mit besserer Formatierung
            template_data = {
                'contact_email': contact_email,
                'action': action_text,
                'contact_name': current_contact.get('name', '❌ Kein Name'),
                'contact_type': 'Firma' if current_contact.get('is_company') else 'Privatperson',
                'contact_phones': current_contact.get('phone') or '❌ Keine Telefonnummer',
                'contact_address': address_str if address_str != "Keine Adresse" else '❌ Keine Adresse',
                'contact_website': current_contact.get('website') or '❌ Keine Website',
                'contact_position': current_contact.get('function') or '❌ Keine Position',
                'contact_language': current_contact.get('lang') or '❌ Keine Sprache',
                'contact_categories': ', '.join(category_names) if category_names else '❌ Keine Kategorien',
                'missing_data': missing_text,
                'odoo_link': f"{self.config['odoo']['url']}/web#id={contact_id}&model=res.partner&view_type=form"
            }

            # Subject und Body aus Templates erstellen
            msg['Subject'] = subject_template.format(**template_data)
            body = body_template.format(**template_data)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # E-Mail senden
            self._send_email(msg)
            self.logger.info(f"✅ Bestätigungs-E-Mail erfolgreich gesendet an: {forwarder_email}")

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Senden der Bestätigungs-E-Mail: {e}")
            self.logger.info("ℹ️ Setze Verarbeitung ohne E-Mail-Versand fort")

    def build_contact_values(self, contact_data: Dict, primary_email: str, category_ids: List[int], existing_contact: Optional[Dict]) -> Tuple[Dict, str]:
        """Baut Kontakt-Datenstruktur für Odoo (FIXED VERSION für Timeline-Notizen)"""

        # FIXED: Korrekte Firmen-Namen-Zuordnung
        is_company = contact_data.get('is_company', False)
        company_name = contact_data.get('company', '').strip()
        full_name = contact_data.get('full_name', '').strip()

        # KRITISCHER FIX: Bei Firmen muss der Firmenname als Hauptname verwendet werden
        if is_company:
            if company_name:
                # Fall 1: Expliziter Firmenname vorhanden
                display_name = company_name
                self.logger.info(f"🏢 Firma: Verwende company-Feld als Hauptname: '{company_name}'")
            elif full_name:
                # Fall 2: full_name enthält wahrscheinlich den Firmennamen
                display_name = full_name
                self.logger.info(f"🏢 Firma: Verwende full_name als Firmenname: '{full_name}'")
            else:
                # Fall 3: Fallback
                display_name = primary_email.split('@')[0].replace('.', ' ').title()
                self.logger.warning(f"🏢 Firma ohne Namen - Fallback: '{display_name}'")
        else:
            # Personen-Logik (unverändert)
            if not full_name:
                first_name = contact_data.get('first_name', '').strip()
                last_name = contact_data.get('last_name', '').strip()
                if first_name or last_name:
                    full_name = f"{first_name} {last_name}".strip()
                else:
                    full_name = primary_email.split('@')[0].replace('.', ' ').title()
            display_name = full_name

            # Bei Personen: Firma separat behandeln
            if company_name:
                self.logger.info(f"👤 Person: '{display_name}' arbeitet bei: '{company_name}'")

        # NEUE BIOGRAPHIE-STRATEGIE: Kompakter Kommentar + separate Timeline-Notiz
        original_biography = contact_data.get('biography', '').strip()  # Für Timeline-Notiz
        confidence = contact_data.get('confidence', 'medium')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

        # Baue kompakten Kommentar (OHNE die lange Biographie)
        comment_parts = []

        # Bei Personen: Firma erwähnen
        if not is_company and company_name:
            comment_parts.append(f"Firma: {company_name}")
            self.logger.info(f"🏢 Firma zum Kommentar hinzugefügt: {company_name}")

        # Kompakter KI-Import-Hinweis
        comment_parts.append(f"[KI-Import {timestamp} - Confidence: {confidence}]")

        # Zusammenfügen - OHNE Biographie im Kommentar
        enhanced_comment = "\n".join(comment_parts)

        # DEBUG: Logs
        self.logger.info(f"📋 Finale Kommentar-Struktur für {primary_email}:")
        self.logger.info(f"   Kommentar: '{enhanced_comment}'")
        self.logger.info(f"   Timeline-Biographie: '{original_biography[:50]}...' ({len(original_biography)} Zeichen)")

        # Sprache konvertieren
        language_code = self.convert_language_to_odoo(contact_data.get('language', 'deutsch'))

        # HAUPTFIX: Korrekte name-Zuordnung
        contact_values = {
            'name': display_name,  # Bei Firmen: Firmenname, bei Personen: Personenname
            'email': primary_email,
            'lang': language_code,
            'is_company': is_company,
            'comment': enhanced_comment  # ← Jetzt kompakt OHNE Biographie
        }

        # DEBUG: Logge die kritischen Werte
        self.logger.info(f"🎯 NAMEN-ZUORDNUNG für {primary_email}:")
        self.logger.info(f"   is_company: {is_company}")
        self.logger.info(f"   company (aus KI): '{company_name}'")
        self.logger.info(f"   full_name (aus KI): '{full_name}'")
        self.logger.info(f"   → name (für Odoo): '{display_name}'")

        # FIXED: Vollständige Adress-Felder aus GPT-strukturierten Daten
        address = contact_data.get('address', {})
        if isinstance(address, dict):
            if address.get('street'):
                contact_values['street'] = address['street']
                self.logger.debug(f"🏠 Straße gesetzt: {address['street']}")
            if address.get('street2'):
                contact_values['street2'] = address['street2']
            if address.get('city'):
                contact_values['city'] = address['city']
                self.logger.debug(f"🏙️ Stadt gesetzt: {address['city']}")
            if address.get('zip'):
                contact_values['zip'] = address['zip']
                self.logger.debug(f"📮 PLZ gesetzt: {address['zip']}")
            if address.get('state'):
                contact_values['state'] = address['state']
            if address.get('country'):
                country_id = self.get_country_code(address['country'])
                if country_id:
                    contact_values['country_id'] = country_id
                    self.logger.debug(f"🌍 Land gesetzt: {address['country']} (ID: {country_id})")

        # Telefon (erstes Telefon als Hauptnummer)
        phones = contact_data.get('phones', [])
        if phones and isinstance(phones, list) and len(phones) > 0:
            contact_values['phone'] = phones[0]
            self.logger.debug(f"📞 Telefon gesetzt: {phones[0]}")

            # Falls mehrere Telefonnummern: in Kommentar erwähnen
            if len(phones) > 1:
                additional_phones = ", ".join(phones[1:])
                enhanced_comment += f"\nWeitere Telefonnummern: {additional_phones}"
                contact_values['comment'] = enhanced_comment

        # Website
        if contact_data.get('website'):
            contact_values['website'] = contact_data['website']
            self.logger.debug(f"🌐 Website gesetzt: {contact_data['website']}")

        # Position/Funktion
        if contact_data.get('position'):
            contact_values['function'] = contact_data['position']
            self.logger.debug(f"💼 Position gesetzt: {contact_data['position']}")

        # Kategorien setzen
        if category_ids:
            contact_values['category_id'] = [(6, 0, category_ids)]
            self.logger.debug(f"🏷️ Kategorien gesetzt: {len(category_ids)} Kategorien")

        # Debug: Alle gesetzten Felder loggen
        self.logger.info(f"📋 Odoo-Felder für {primary_email}:")
        for field, value in contact_values.items():
            if field != 'comment':  # Kommentar ist zu lang für Log
                self.logger.info(f"   {field}: {value}")

        # RÜCKGABE: contact_values + original_biography für Timeline-Notiz
        return contact_values, original_biography

    def get_update_values(self, existing_contact: Dict, new_values: Dict) -> Dict:
        """Ermittelt Update-Werte (FIXED für Firmen-Namen-Updates + Biographie-Erhaltung)"""
        update_values = {}

        # FIXED: Firmen-Namen-Updates intelligenter handhaben
        existing_name = existing_contact.get('name', '').strip()
        new_name = new_values.get('name', '').strip()
        existing_is_company = existing_contact.get('is_company', False)
        new_is_company = new_values.get('is_company', False)

        # Sicherheitscheck: Konvertiere zu String falls nötig
        if not isinstance(existing_name, str):
            existing_name = str(existing_name).strip() if existing_name else ''
        if not isinstance(new_name, str):
            new_name = str(new_name).strip() if new_name else ''

        # Firmen-Name-Update-Logik
        if new_is_company and new_name:
            # Bei Firmen: Name sollte immer der beste verfügbare Firmenname sein
            should_update_name = (
                not existing_name or  # Kein Name vorhanden
                len(new_name.split()) > len(existing_name.split()) or  # Neuer Name vollständiger
                any(placeholder in existing_name.lower() for placeholder in ['unknown', 'contact', '@']) or  # Placeholder-Name
                (not existing_is_company and new_is_company)  # Wechsel von Person zu Firma
            )

            if should_update_name:
                update_values['name'] = new_name
                self.logger.info(f"🏢 Firmen-Name aktualisiert: '{existing_name}' → '{new_name}'")

        elif not new_is_company and new_name:
            # Bei Personen: Normale Update-Logik
            if (not existing_name or
                len(new_name.split()) > len(existing_name.split()) or
                any(placeholder in existing_name.lower() for placeholder in ['unknown', 'contact', '@'])):
                update_values['name'] = new_name
                self.logger.info(f"👤 Personen-Name aktualisiert: '{existing_name}' → '{new_name}'")

        # is_company Flag aktualisieren
        if new_is_company and not existing_is_company:
            update_values['is_company'] = True
            self.logger.info(f"🏢 Kontakt als Firma markiert")

        # FIXED: Erweiterte complement_fields - STREET hinzugefügt!
        complement_fields = ['phone', 'street', 'city', 'zip', 'website', 'function']

        for field in complement_fields:
            if field in new_values and new_values[field]:
                existing_value = existing_contact.get(field)
                if not existing_value or (isinstance(existing_value, str) and existing_value.strip() == ''):
                    update_values[field] = new_values[field]
                    self.logger.info(f"📝 {field} ergänzt: {new_values[field]}")

        # Sprache separat behandeln (da Boolean in Odoo)
        if 'lang' in new_values and new_values['lang']:
            existing_lang = existing_contact.get('lang')
            if not existing_lang:  # Nur setzen wenn leer
                update_values['lang'] = new_values['lang']
                self.logger.info(f"📝 Sprache ergänzt: {new_values['lang']}")

        # FIXED: Country separat behandeln
        if 'country_id' in new_values and new_values['country_id']:
            existing_country = existing_contact.get('country_id')
            if not existing_country:  # Nur setzen wenn leer
                update_values['country_id'] = new_values['country_id']
                self.logger.info(f"📝 Land ergänzt: {new_values['country_id']}")

        # FIXED: Kommentar intelligent erweitern (aber NICHT Biographie - das macht Timeline-Notiz)
        if 'comment' in new_values:
            existing_comment = existing_contact.get('comment', '').strip()
            new_comment = new_values['comment'].strip()

            # Sicherheitscheck: Konvertiere zu String falls nötig
            if not isinstance(existing_comment, str):
                existing_comment = str(existing_comment).strip() if existing_comment else ''
            if not isinstance(new_comment, str):
                new_comment = str(new_comment).strip() if new_comment else ''

            # INTELLIGENTE KOMMENTAR-BEHANDLUNG (Timeline-Notizen machen die Biographie)
            if existing_comment:
                # Prüfe ob neuer Kommentar bereits in bestehendem enthalten ist
                if new_comment.strip() not in existing_comment:
                    # Neuen Kommentar hinzufügen
                    combined_comment = f"{existing_comment}\n--- Ergänzung ---\n{new_comment}"
                    update_values['comment'] = combined_comment
                    self.logger.info("📝 Kommentar erweitert mit neuen Informationen")
                else:
                    self.logger.info("📝 Kommentar bereits vorhanden - überspringe")
            else:
                # Kein bestehender Kommentar - neuen setzen
                update_values['comment'] = new_comment
                self.logger.info("📝 Neuer Kommentar hinzugefügt")

        # Kategorien zusammenführen
        if 'category_id' in new_values:
            existing_cat_ids = set(cat[0] if isinstance(cat, (list, tuple)) else cat
                                for cat in existing_contact.get('category_id', []))
            new_cat_ids = set(new_values['category_id'][0][2])

            combined_cat_ids = list(existing_cat_ids.union(new_cat_ids))
            if combined_cat_ids != list(existing_cat_ids):
                update_values['category_id'] = [(6, 0, combined_cat_ids)]
                self.logger.info(f"🏷️ Kategorien erweitert: {new_cat_ids - existing_cat_ids}")

        # Debug: Zeige was geupdatet wird
        if update_values:
            self.logger.info(f"🔄 Update-Felder für {existing_contact.get('email', 'N/A')}:")
            for field, value in update_values.items():
                if field != 'comment':  # Kommentar ist zu lang
                    self.logger.info(f"   {field}: {value}")
        else:
            self.logger.info("ℹ️ Keine Updates nötig - Kontakt bereits vollständig")

        return update_values

    def get_country_code(self, country_name: str) -> Optional[int]:
        """Konvertiert Ländernamen zu Odoo-Country-IDs"""
        try:
            country_iso_map = {
                'russia': 'RU', 'deutschland': 'DE', 'germany': 'DE',
                'schweiz': 'CH', 'switzerland': 'CH', 'österreich': 'AT',
                'austria': 'AT', 'usa': 'US', 'united states': 'US'
            }

            country_lower = country_name.lower().strip()
            iso_code = country_iso_map.get(country_lower)

            if iso_code:
                try:
                    country_ids = self.odoo_models.execute_kw(
                        self.config['odoo']['database'],
                        self.odoo_uid,
                        self.config['odoo']['password'],
                        'res.country', 'search',
                        [[['code', '=', iso_code]]]
                    )

                    if country_ids:
                        country_id = country_ids[0]
                        self.logger.info(f"🌍 Land erkannt: {country_name} → {iso_code} (ID: {country_id})")
                        return country_id

                except Exception as e:
                    self.logger.warning(f"⚠️ Odoo-Land-Suche fehlgeschlagen: {e}")
                    return None

            return None

        except Exception as e:
            self.logger.error(f"❌ Fehler bei Land-Mapping: {e}")
            return None

    def _clean_biography(self, biography_text: str) -> str:
        """Bereinigt Biographie von HTML-Tags und kürzt sie"""
        if not biography_text:
            return '❌ Keine Biographie'

        # HTML-Tags entfernen
        import re
        clean_text = re.sub(r'<[^>]+>', '', str(biography_text))

        # Länge begrenzen
        if len(clean_text) > 500:
            clean_text = clean_text[:500] + '...'

        return clean_text

    def convert_language_to_odoo(self, language: str) -> str:
        """Konvertiert Sprache zu Odoo-Sprachcode"""
        language_map = {
            'deutsch': 'de_DE', 'german': 'de_DE', 'english': 'en_US',
            'englisch': 'en_US', 'français': 'fr_FR', 'french': 'fr_FR',
            'italiano': 'it_IT', 'italian': 'it_IT', 'español': 'es_ES',
            'spanish': 'es_ES', 'русский': 'ru_RU', 'russian': 'ru_RU'
        }

        return language_map.get(language.lower(), 'de_DE')
