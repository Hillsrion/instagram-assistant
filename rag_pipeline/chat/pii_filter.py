"""
PII (Personally Identifiable Information) Filter.
Detects and masks sensitive information in text.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum


class PIIType(str, Enum):
    PHONE_FR = "phone_fr"        # French phone numbers
    PHONE_INTL = "phone_intl"    # International phone numbers
    EMAIL = "email"
    IBAN = "iban"
    CREDIT_CARD = "credit_card"
    ADDRESS = "address"
    SSN_FR = "ssn_fr"           # French social security number


@dataclass
class PIIMatch:
    """A detected PII match."""
    pii_type: PIIType
    original_text: str
    start: int
    end: int
    masked_text: str


# Mask labels for each PII type
MASK_LABELS = {
    PIIType.PHONE_FR: "[TELEPHONE MASQUE]",
    PIIType.PHONE_INTL: "[TELEPHONE MASQUE]",
    PIIType.EMAIL: "[EMAIL MASQUE]",
    PIIType.IBAN: "[IBAN MASQUE]",
    PIIType.CREDIT_CARD: "[CARTE MASQUEE]",
    PIIType.ADDRESS: "[ADRESSE MASQUEE]",
    PIIType.SSN_FR: "[NSS MASQUE]",
}


class PIIFilter:
    """
    Detect and mask PII in text.

    Supports:
    - French and international phone numbers
    - Email addresses
    - IBAN numbers
    - Credit card numbers
    - French addresses (partial)
    - French social security numbers
    """

    def __init__(self):
        # Compile regex patterns
        self.patterns = {
            # French phone: 06 12 34 56 78, 0612345678, +33 6 12 34 56 78
            PIIType.PHONE_FR: re.compile(
                r'(?:\+33[\s.-]?|0)([1-9])(?:[\s.-]?\d{2}){4}',
                re.IGNORECASE
            ),

            # International phone (generic): +1-234-567-8901, etc.
            PIIType.PHONE_INTL: re.compile(
                r'\+[1-9]\d{0,2}[-.\s]?(?:\d[-.\s]?){7,14}\d',
                re.IGNORECASE
            ),

            # Email addresses
            PIIType.EMAIL: re.compile(
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                re.IGNORECASE
            ),

            # IBAN (French and general European)
            PIIType.IBAN: re.compile(
                r'[A-Z]{2}\d{2}[\s]?(?:[A-Z0-9]{4}[\s]?){2,7}[A-Z0-9]{1,4}',
                re.IGNORECASE
            ),

            # Credit card numbers (13-19 digits, possibly with spaces/dashes)
            PIIType.CREDIT_CARD: re.compile(
                r'(?:\d{4}[-\s]?){3,4}\d{1,4}',
                re.IGNORECASE
            ),

            # French SSN (numero de securite sociale): 1 85 12 75 115 234 45
            PIIType.SSN_FR: re.compile(
                r'[12][\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{3}[\s.-]?\d{3}(?:[\s.-]?\d{2})?',
                re.IGNORECASE
            ),
        }

        # Address pattern (French) - less precise, matches common patterns
        self.address_pattern = re.compile(
            r'\d{1,4}(?:[\s,]+(?:rue|avenue|boulevard|place|chemin|impasse|allée|passage|'
            r'av\.|bd\.|pl\.|ch\.))[\s,]+[A-Za-zÀ-ÿ\s\'-]+(?:[\s,]+\d{5}[\s,]+[A-Za-zÀ-ÿ\s\'-]+)?',
            re.IGNORECASE
        )

    def detect(self, text: str) -> List[PIIMatch]:
        """
        Detect all PII in the text.

        Args:
            text: Input text to scan

        Returns:
            List of PIIMatch objects, sorted by position
        """
        matches = []

        # Check all pattern types
        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                # Validate credit card (must be mostly digits)
                if pii_type == PIIType.CREDIT_CARD:
                    digits = re.sub(r'\D', '', match.group())
                    if len(digits) < 13 or len(digits) > 19:
                        continue
                    # Basic Luhn check could be added here

                # Validate IBAN (basic check)
                if pii_type == PIIType.IBAN:
                    iban = match.group().replace(' ', '')
                    if len(iban) < 15 or len(iban) > 34:
                        continue

                matches.append(PIIMatch(
                    pii_type=pii_type,
                    original_text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    masked_text=MASK_LABELS[pii_type]
                ))

        # Check address pattern separately
        for match in self.address_pattern.finditer(text):
            matches.append(PIIMatch(
                pii_type=PIIType.ADDRESS,
                original_text=match.group(),
                start=match.start(),
                end=match.end(),
                masked_text=MASK_LABELS[PIIType.ADDRESS]
            ))

        # Sort by position and remove overlaps (keep longest match)
        matches.sort(key=lambda m: (m.start, -(m.end - m.start)))
        filtered = []
        last_end = -1

        for m in matches:
            if m.start >= last_end:
                filtered.append(m)
                last_end = m.end

        return filtered

    def mask(self, text: str) -> Tuple[str, List[PIIMatch]]:
        """
        Mask all PII in the text.

        Args:
            text: Input text

        Returns:
            Tuple of (masked_text, list of matches)
        """
        matches = self.detect(text)

        if not matches:
            return text, []

        # Build masked text (process in reverse order to preserve positions)
        result = text
        for match in reversed(matches):
            result = result[:match.start] + match.masked_text + result[match.end:]

        return result, matches

    def has_pii(self, text: str) -> bool:
        """Check if text contains any PII."""
        return len(self.detect(text)) > 0

    def get_pii_summary(self, text: str) -> dict:
        """Get a summary of PII found in text."""
        matches = self.detect(text)

        summary = {
            'total_count': len(matches),
            'by_type': {},
            'positions': []
        }

        for m in matches:
            t = m.pii_type.value
            summary['by_type'][t] = summary['by_type'].get(t, 0) + 1
            summary['positions'].append({
                'type': t,
                'start': m.start,
                'end': m.end
            })

        return summary
