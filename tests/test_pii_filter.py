"""
Tests for pii_filter.py module.
Detection and masking of Personally Identifiable Information (PII).
"""
import unittest
from rag_pipeline.pii_filter import PIIFilter, PIIType, PIIMatch


class TestPIIFilter(unittest.TestCase):

    def setUp(self):
        self.filter = PIIFilter()

    # --- Tests French Phone Detection ---
    def test_detect_french_phone_with_spaces(self):
        """Detect French phone number with spaces: 06 12 34 56 78"""
        text = "Appelle-moi au 06 12 34 56 78"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.PHONE_FR)
        self.assertIn("06 12 34 56 78", matches[0].original_text)

    def test_detect_french_phone_compact(self):
        """Detect compact French phone number: 0612345678"""
        text = "Tel: 0612345678"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.PHONE_FR)

    def test_detect_french_phone_international(self):
        """Detect international format French phone number: +33 6 12 34 56 78"""
        text = "Contact: +33 6 12 34 56 78"
        matches = self.filter.detect(text)
        self.assertTrue(len(matches) >= 1)
        # Can be detected as PHONE_FR or PHONE_INTL

    # --- Tests Email Detection ---
    def test_detect_email(self):
        """Detect standard email address"""
        text = "Mon email: test@example.com"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.EMAIL)
        self.assertEqual(matches[0].original_text, "test@example.com")

    def test_detect_email_complex(self):
        """Detect email with subdomain and special chars"""
        text = "Contact: jean.dupont+test@mail.company.fr"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.EMAIL)

    # --- Tests IBAN Detection ---
    def test_detect_iban_french(self):
        """Detect French IBAN"""
        text = "IBAN: FR76 3000 6000 0112 3456 7890 189"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.IBAN)

    def test_detect_iban_no_spaces(self):
        """Detect IBAN without spaces"""
        text = "IBAN: FR7630006000011234567890189"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.IBAN)

    # --- Tests Credit Card Detection ---
    def test_detect_credit_card(self):
        """Detect credit card number"""
        text = "Carte: 4111 1111 1111 1111"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.CREDIT_CARD)

    def test_detect_credit_card_no_spaces(self):
        """Detect credit card number without spaces"""
        text = "CB: 4111111111111111"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.CREDIT_CARD)

    # --- Tests Masking ---
    def test_mask_single_pii(self):
        """Mask single PII"""
        text = "Mon email est user@test.com"
        masked, matches = self.filter.mask(text)
        self.assertIn("[EMAIL MASQUE]", masked)
        self.assertNotIn("user@test.com", masked)
        self.assertEqual(len(matches), 1)

    def test_mask_multiple_pii(self):
        """Mask multiple PII in text"""
        text = "Tel: 06 12 34 56 78, Email: test@example.com"
        masked, matches = self.filter.mask(text)
        self.assertIn("[TELEPHONE MASQUE]", masked)
        self.assertIn("[EMAIL MASQUE]", masked)
        self.assertEqual(len(matches), 2)

    def test_mask_no_pii(self):
        """No masking if no PII"""
        text = "Bonjour, comment ça va ?"
        masked, matches = self.filter.mask(text)
        self.assertEqual(masked, text)
        self.assertEqual(len(matches), 0)

    # --- Tests Utilities ---
    def test_has_pii_true(self):
        """has_pii returns True if PII present"""
        self.assertTrue(self.filter.has_pii("Email: test@example.com"))

    def test_has_pii_false(self):
        """has_pii returns False if no PII"""
        self.assertFalse(self.filter.has_pii("Texte normal sans info perso"))

    def test_get_pii_summary(self):
        """get_pii_summary returns structured summary"""
        text = "Tel: 06 12 34 56 78, Email: a@b.com"
        summary = self.filter.get_pii_summary(text)
        self.assertEqual(summary['total_count'], 2)
        self.assertIn('by_type', summary)
        self.assertIn('positions', summary)

    # --- Tests Edge Cases ---
    def test_no_false_positive_on_short_numbers(self):
        """No false positive on short numbers (zip codes)"""
        text = "Code postal: 75001"
        matches = self.filter.detect(text)
        # Should not detect zip code as phone number
        phone_matches = [m for m in matches if m.pii_type in (PIIType.PHONE_FR, PIIType.PHONE_INTL)]
        self.assertEqual(len(phone_matches), 0)


if __name__ == '__main__':
    unittest.main()