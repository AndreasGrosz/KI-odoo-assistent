#!/usr/bin/env python3
"""
KI-Datenextraktion für Kontaktdaten
Handles OpenAI GPT Integration und Datenvalidierung mit Smart-Strategy
"""

import openai
import json
import re
import logging
from typing import Dict, List


class DataExtractor:
    def __init__(self, config: dict, logger: logging.Logger, prompts: dict):
        """Initialisiert Datenextraktor"""
        self.config = config
        self.logger = logger
        self.prompts = prompts

    def apply_smart_strategy(self, email_text: str) -> str:
        """Smart-Strategy: Erste 2000 + Letzte 1000 Zeichen für Kostenoptimierung"""

        self.logger.info(f"🔧 Smart-Strategy Input: {len(email_text)} Zeichen")

        strategy = self.config.get('smart_strategy', {})
        if not strategy.get('enabled', False):
            self.logger.warning("⚠️ Smart-Strategy deaktiviert - verwende Standard-Limit")
            max_length = self.config.get('assistant', {}).get('max_email_length', 3000)
            return email_text[:max_length]

        head_chars = strategy.get('head_chars', 2000)
        footer_chars = strategy.get('footer_chars', 1000)
        max_total = strategy.get('max_total_chars', 3000)

        if len(email_text) <= max_total:
            self.logger.info(f"📧 Kurze E-Mail ({len(email_text)} Zeichen) - vollständig verarbeitet")
            return email_text

        # Erste N Zeichen (Head)
        head = email_text[:head_chars].rstrip()

        # Letzte M Zeichen (Footer)
        footer = email_text[-footer_chars:].lstrip()

        # Separator mit Info über übersprungene Zeichen
        skipped_chars = len(email_text) - head_chars - footer_chars
        separator = f"\n\n[...{skipped_chars} Zeichen übersprungen für Kostenoptimierung...]\n\n"

        result = head + separator + footer

        self.logger.info(f"🔧 Smart-Strategy angewendet:")
        self.logger.info(f"   📄 Head: {len(head)} Zeichen")
        self.logger.info(f"   ⏭️ Übersprungen: {skipped_chars} Zeichen")
        self.logger.info(f"   📦 Footer: {len(footer)} Zeichen")
        self.logger.info(f"   📊 Total: {len(result)} Zeichen (Original: {len(email_text)})")

        return result

    def extract_contact_data(self, email_text: str, biography: str, sender_email: str) -> Dict:
        """Extrahiert Kontaktdaten mit OpenAI GPT (mit Smart-Strategy)"""

        # Smart-Strategy anwenden
        optimized_text = self.apply_smart_strategy(email_text)

        # Prompt aus YAML laden
        email_prompt_config = self.prompts.get('email_extraction', {})
        system_prompt = email_prompt_config.get('system', 'Du bist ein Experte für Kontaktdaten-Extraktion.')

        user_template = email_prompt_config.get('user_template', '''
Du bist ein Experte für die Extraktion von Kontaktdaten aus E-Mails.

ABSENDER-EMAIL: {sender_email}
BIOGRAPHIE: {biography}
E-MAIL-INHALT: {email_text}

Extrahiere alle verfügbaren Kontaktdaten als JSON.
        ''')

        # Template mit optimierten Daten füllen
        user_prompt = user_template.format(
            sender_email=sender_email,
            biography=biography,
            email_text=optimized_text
        )

        try:
            response = openai.chat.completions.create(
                model=self.config['openai']['model'],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.config['openai']['max_tokens'],
                temperature=self.config['openai']['temperature']
            )

            result_text = response.choices[0].message.content
            if not result_text:
                self.logger.error("❌ Leere GPT-Antwort erhalten")
                return self.create_fallback_contact_data(sender_email, biography)

            result_text = result_text.strip()
            self.logger.info(f"🤖 GPT Antwort (Smart-Strategy): {result_text}")

            # JSON-Parsing
            contact_data = self.parse_gpt_response(result_text)
            if not contact_data:
                return self.create_fallback_contact_data(sender_email, biography)

            self.logger.info("✅ JSON erfolgreich geparst - verwende GPT-Daten!")
            contact_data = self.validate_and_clean_contact_data(contact_data, sender_email)

            confidence = contact_data.get('confidence', 'medium')
            self.logger.info(f"✅ Kontaktdaten extrahiert (Confidence: {confidence})")

            return contact_data

        except Exception as e:
            self.logger.error(f"❌ Fehler bei Datenextraktion: {e}")
            return self.create_fallback_contact_data(sender_email, biography)

    def extract_manual_contact_data(self, email_text: str, biography: str, sender_email: str) -> Dict:
        """Extrahiert Kontaktdaten aus manuellem Input (mit YAML-Prompts)"""

        # Smart-Strategy auch für manuellen Input
        optimized_text = self.apply_smart_strategy(email_text)

        # Prompt aus YAML laden
        manual_prompt_config = self.prompts.get('manual_extraction', {})
        system_prompt = manual_prompt_config.get('system', 'Du bist ein Experte für manuelle Kontaktdaten-Extraktion.')

        user_template = manual_prompt_config.get('user_template', '''
Du bist ein Experte für die Extraktion von Kontaktdaten aus manuellem Text.

GENERIERTE EMAIL: {sender_email}
TEXT-INHALT: {email_text}

Extrahiere alle verfügbaren Kontaktdaten als JSON.
        ''')

        # Template mit Daten füllen
        user_prompt = user_template.format(
            sender_email=sender_email,
            email_text=optimized_text
        )

        try:
            response = openai.chat.completions.create(
                model=self.config['openai']['model'],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.config['openai']['max_tokens'],
                temperature=self.config['openai']['temperature']
            )

            result_text = response.choices[0].message.content
            if not result_text:
                self.logger.error("❌ Leere GPT-Antwort erhalten")
                return self.create_fallback_manual_contact_data(sender_email, biography)

            result_text = result_text.strip()
            self.logger.info(f"🤖 GPT Antwort (Manual-Smart): {result_text}")

            contact_data = self.parse_gpt_response(result_text)
            if not contact_data:
                return self.create_fallback_manual_contact_data(sender_email, biography)

            self.logger.info("✅ JSON erfolgreich geparst - verwende GPT-Daten (manuell)!")
            contact_data = self.validate_and_clean_manual_contact_data(contact_data, sender_email)

            confidence = contact_data.get('confidence', 'medium')
            self.logger.info(f"✅ Manueller Kontakt extrahiert (Confidence: {confidence})")

            return contact_data

        except Exception as e:
            self.logger.error(f"❌ Fehler bei manueller Datenextraktion: {e}")
            return self.create_fallback_manual_contact_data(sender_email, biography)

    def parse_gpt_response(self, result_text: str) -> Dict:
        """Parst GPT-Response zu JSON (zentrale Methode)"""
        try:
            # Versuch 1: Direktes JSON-Parsing
            return json.loads(result_text)
        except json.JSONDecodeError:
            try:
                # Versuch 2: JSON zwischen Backticks
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', result_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                try:
                    # Versuch 3: Erstes vollständiges JSON-Objekt
                    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        self.logger.error(f"❌ JSON-Parsing komplett fehlgeschlagen. GPT Antwort: {result_text}")
        return None

    def validate_and_clean_contact_data(self, contact_data: Dict, sender_email: str) -> Dict:
        """Validiert und bereinigt extrahierte Kontaktdaten"""

        # Null-Werte zu leeren Strings konvertieren
        for key, value in contact_data.items():
            if value is None:
                contact_data[key] = ''

        # E-Mail-Behandlung
        emails = contact_data.get('emails', [])
        if sender_email:
            emails = [e for e in emails if e != sender_email]
            emails.insert(0, sender_email)

        valid_emails = []
        for email_addr in emails:
            if (email_addr and isinstance(email_addr, str) and '@' in email_addr and
                'ki-kontakt-admin' not in email_addr and 'ki-adress-admin' not in email_addr and
                '@5gfrei.ch' not in email_addr and '@andreas-gross.ch' not in email_addr):
                valid_emails.append(email_addr)

        contact_data['emails'] = valid_emails[:3]

        # Telefonnummern normalisieren
        phones = contact_data.get('phones', [])
        normalized_phones = []
        for phone in phones:
            if phone and isinstance(phone, str):
                clean_phone = re.sub(r'[^\d\+\-\(\)\s]', '', phone.strip())
                if clean_phone and len(clean_phone) >= 6:
                    normalized_phones.append(clean_phone)
        contact_data['phones'] = normalized_phones

        # Kategorien normalisieren
        categories = contact_data.get('categories', [])
        normalized_categories = []

        for cat in categories:
            if cat and isinstance(cat, str):
                clean_cat = cat.lower().strip('#').strip()
                if clean_cat:
                    normalized_categories.append(clean_cat)

        # Hashtag-Extraktion aus Biographie
        biography = contact_data.get('biography', '') or ''
        if biography and isinstance(biography, str):
            clean_biography = re.sub(r'#[a-zA-ZäöüÄÖÜß0-9]+', '', biography).strip()
            clean_biography = re.sub(r'\s+', ' ', clean_biography).strip()
            contact_data['biography'] = clean_biography

            hashtag_pattern = r'#([a-zA-ZäöüÄÖÜß][a-zA-ZäöüÄÖÜß0-9]*)'
            found_hashtags = re.findall(hashtag_pattern, biography)
            for hashtag in found_hashtags:
                clean_hashtag = hashtag.lower().strip()
                if clean_hashtag and clean_hashtag not in normalized_categories:
                    normalized_categories.append(clean_hashtag)
                    self.logger.info(f"🏷️ Hashtag gefunden: #{clean_hashtag}")

        contact_data['categories'] = normalized_categories

        # Adresse validieren
        address = contact_data.get('address', {})
        if address and isinstance(address, dict):
            address_str = f"{address.get('street', '')} {address.get('city', '')} {address.get('zip', '')}".lower()
            own_address_indicators = ['althusweg 12', 'morgarten', '6315', 'andreas groß', 'andreas gross', '5gfrei']
            if any(indicator in address_str for indicator in own_address_indicators):
                self.logger.warning(f"⚠️ Eigene Adresse erkannt und entfernt: {address}")
                contact_data['address'] = {}
            else:
                for key in ['street', 'street2', 'city', 'zip', 'state', 'country']:
                    if address.get(key) is None:
                        address[key] = ''
                contact_data['address'] = address
        else:
            contact_data['address'] = {}

        # Website validieren
        website = contact_data.get('website', '') or ''
        if website and isinstance(website, str) and website.strip():
            website_lower = website.lower()
            own_domains = ['5gfrei.ch', 'inggross.de', 'standortdatenblatt.ch', 'swiss-ecommerce.ch']

            if any(domain in website_lower for domain in own_domains):
                self.logger.warning(f"⚠️ Eigene Website erkannt und entfernt: {website}")
                contact_data['website'] = ''
            elif not website.startswith('http'):
                website = f"https://{website}"
                contact_data['website'] = website if self.is_valid_url(website) else ''
            else:
                contact_data['website'] = website if self.is_valid_url(website) else ''
        else:
            contact_data['website'] = ''

        return contact_data

    def validate_and_clean_manual_contact_data(self, contact_data: Dict, sender_email: str) -> Dict:
        """Validiert und bereinigt extrahierte Kontaktdaten aus manuellem Input"""

        # Null-Werte konvertieren
        for key, value in contact_data.items():
            if value is None:
                contact_data[key] = ''

        # E-Mail-Behandlung für manuellen Input
        emails = contact_data.get('emails', [])
        valid_emails = []

        for email_addr in emails:
            if (email_addr and isinstance(email_addr, str) and '@' in email_addr and
                'manual-contact.local' not in email_addr and 'placeholder.local' not in email_addr and
                'ki-kontakt-admin' not in email_addr and 'ki-adress-admin' not in email_addr and
                '@5gfrei.ch' not in email_addr and '@andreas-gross.ch' not in email_addr):
                valid_emails.append(email_addr)

        if not valid_emails:
            valid_emails = [sender_email]

        contact_data['emails'] = valid_emails[:3]

        # Kategorien und Biographie wie bei normalem Input behandeln
        return self.validate_and_clean_contact_data(contact_data, sender_email)

    def is_valid_url(self, url: str) -> bool:
        """Einfache URL-Validierung"""
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None

    def create_fallback_contact_data(self, sender_email: str, biography: str) -> Dict:
        """Erstellt intelligente Fallback-Kontaktdaten bei Parsing-Fehlern"""

        name_part = sender_email.split('@')[0] if sender_email else "Unknown"

        if '.' in name_part:
            parts = name_part.split('.')
            if len(parts) == 2:
                first_name = parts[0].capitalize()
                last_name = parts[1].capitalize()
                full_name = f"{first_name} {last_name}"
            else:
                full_name = name_part.replace('.', ' ').title()
                first_name = ''
                last_name = ''
        else:
            full_name = name_part.capitalize()
            first_name = ''
            last_name = ''

        categories = []
        if biography:
            hashtag_pattern = r'#([a-zA-ZäöüÄÖÜß][a-zA-ZäöüÄÖÜß]*)'
            found_hashtags = re.findall(hashtag_pattern, biography)
            categories = [tag.lower() for tag in found_hashtags]
            if categories:
                self.logger.info(f"🏷️ Fallback-Hashtags gefunden: {categories}")

        return {
            'first_name': first_name,
            'last_name': last_name,
            'full_name': full_name,
            'emails': [sender_email] if sender_email else [],
            'phones': [],
            'address': {},
            'website': '',
            'company': '',
            'position': '',
            'language': 'deutsch',
            'categories': categories,
            'biography': biography,
            'confidence': 'fallback'
        }

    def create_fallback_manual_contact_data(self, sender_email: str, biography: str) -> Dict:
        """Erstellt intelligente Fallback-Kontaktdaten für manuellen Input"""

        full_name = "Manueller Kontakt"

        if biography:
            lines = biography.split('\n')
            for line in lines:
                line = line.strip()
                if (len(line.split()) >= 2 and len(line.split()) <= 4 and
                    '@' not in line and not re.search(r'\d{3,}', line) and
                    not line.startswith('#')):
                    full_name = line
                    break

        categories = []
        if biography:
            hashtag_pattern = r'#([a-zA-ZäöüÄÖÜß][a-zA-ZäöüÄÖÜß0-9]*)'
            found_hashtags = re.findall(hashtag_pattern, biography)
            categories = [tag.lower() for tag in found_hashtags]
            if categories:
                self.logger.info(f"🏷️ Fallback-Hashtags gefunden: {categories}")

        clean_biography = biography
        if biography:
            clean_biography = re.sub(r'#[a-zA-ZäöüÄÖÜß0-9]+', '', biography).strip()
            clean_biography = re.sub(r'\s+', ' ', clean_biography).strip()

        return {
            'first_name': '',
            'last_name': '',
            'full_name': full_name,
            'emails': [sender_email] if sender_email else [],
            'phones': [],
            'address': {},
            'website': '',
            'company': '',
            'position': '',
            'is_company': False,
            'language': 'deutsch',
            'categories': categories,
            'biography': clean_biography,
            'confidence': 'fallback_manual'
        }

    def log_extracted_data(self, contact_data: Dict):
        """Loggt extrahierte Kontaktdaten (erweitert)"""
        try:
            name = contact_data.get('full_name', 'N/A')
            emails = contact_data.get('emails', [])
            phones = contact_data.get('phones', [])
            categories = contact_data.get('categories', [])
            confidence = contact_data.get('confidence', 'unknown')
            language = contact_data.get('language', 'N/A')

            address = contact_data.get('address', {})
            if isinstance(address, dict):
                address_str = f"{address.get('street', '')} {address.get('city', '')} {address.get('zip', '')} {address.get('country', '')}".strip()
            else:
                address_str = str(address) if address else 'N/A'

            self.logger.info(f"🎯 Name: {name}")
            self.logger.info(f"📧 E-Mails: {', '.join(emails) if emails else 'Keine'}")
            self.logger.info(f"📞 Telefon: {', '.join(phones) if phones else 'Keine'}")
            self.logger.info(f"🏠 Adresse: {address_str}")
            self.logger.info(f"🌍 Sprache: {language}")
            self.logger.info(f"🏷️ Kategorien: {', '.join(categories) if categories else 'Keine'}")
            self.logger.info(f"🎲 Confidence: {confidence}")

        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Logging: {e}")
