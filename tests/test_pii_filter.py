"""
Tests pour le module pii_filter.py
Détection et masquage des informations personnelles (PII).
"""
import unittest
from rag_pipeline.pii_filter import PIIFilter, PIIType, PIIMatch


class TestPIIFilter(unittest.TestCase):

    def setUp(self):
        self.filter = PIIFilter()

    # --- Tests de détection téléphone FR ---
    def test_detect_french_phone_with_spaces(self):
        """Détection numéro FR avec espaces: 06 12 34 56 78"""
        text = "Appelle-moi au 06 12 34 56 78"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.PHONE_FR)
        self.assertIn("06 12 34 56 78", matches[0].original_text)

    def test_detect_french_phone_compact(self):
        """Détection numéro FR compact: 0612345678"""
        text = "Tel: 0612345678"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.PHONE_FR)

    def test_detect_french_phone_international(self):
        """Détection numéro FR format international: +33 6 12 34 56 78"""
        text = "Contact: +33 6 12 34 56 78"
        matches = self.filter.detect(text)
        self.assertTrue(len(matches) >= 1)
        # Peut être détecté comme PHONE_FR ou PHONE_INTL

    # --- Tests de détection email ---
    def test_detect_email(self):
        """Détection adresse email standard"""
        text = "Mon email: test@example.com"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.EMAIL)
        self.assertEqual(matches[0].original_text, "test@example.com")

    def test_detect_email_complex(self):
        """Détection email avec sous-domaine et caractères spéciaux"""
        text = "Contact: jean.dupont+test@mail.company.fr"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.EMAIL)

    # --- Tests de détection IBAN ---
    def test_detect_iban_french(self):
        """Détection IBAN français"""
        text = "IBAN: FR76 3000 6000 0112 3456 7890 189"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.IBAN)

    def test_detect_iban_no_spaces(self):
        """Détection IBAN sans espaces"""
        text = "IBAN: FR7630006000011234567890189"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.IBAN)

    # --- Tests de détection carte bancaire ---
    def test_detect_credit_card(self):
        """Détection numéro de carte bancaire"""
        text = "Carte: 4111 1111 1111 1111"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.CREDIT_CARD)

    def test_detect_credit_card_no_spaces(self):
        """Détection carte bancaire sans espaces"""
        text = "CB: 4111111111111111"
        matches = self.filter.detect(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].pii_type, PIIType.CREDIT_CARD)

    # --- Tests de masquage ---
    def test_mask_single_pii(self):
        """Masquage d'un seul PII"""
        text = "Mon email est user@test.com"
        masked, matches = self.filter.mask(text)
        self.assertIn("[EMAIL MASQUE]", masked)
        self.assertNotIn("user@test.com", masked)
        self.assertEqual(len(matches), 1)

    def test_mask_multiple_pii(self):
        """Masquage de plusieurs PII dans un texte"""
        text = "Tel: 06 12 34 56 78, Email: test@example.com"
        masked, matches = self.filter.mask(text)
        self.assertIn("[TELEPHONE MASQUE]", masked)
        self.assertIn("[EMAIL MASQUE]", masked)
        self.assertEqual(len(matches), 2)

    def test_mask_no_pii(self):
        """Aucun masquage si pas de PII"""
        text = "Bonjour, comment ça va ?"
        masked, matches = self.filter.mask(text)
        self.assertEqual(masked, text)
        self.assertEqual(len(matches), 0)

    # --- Tests utilitaires ---
    def test_has_pii_true(self):
        """has_pii retourne True si PII présent"""
        self.assertTrue(self.filter.has_pii("Email: test@example.com"))

    def test_has_pii_false(self):
        """has_pii retourne False si aucun PII"""
        self.assertFalse(self.filter.has_pii("Texte normal sans info perso"))

    def test_get_pii_summary(self):
        """get_pii_summary retourne un résumé structuré"""
        text = "Tel: 06 12 34 56 78, Email: a@b.com"
        summary = self.filter.get_pii_summary(text)
        self.assertEqual(summary['total_count'], 2)
        self.assertIn('by_type', summary)
        self.assertIn('positions', summary)

    # --- Tests edge cases ---
    def test_no_false_positive_on_short_numbers(self):
        """Pas de faux positif sur les codes courts"""
        text = "Code postal: 75001"
        matches = self.filter.detect(text)
        # Ne devrait pas détecter un code postal comme téléphone
        phone_matches = [m for m in matches if m.pii_type in (PIIType.PHONE_FR, PIIType.PHONE_INTL)]
        self.assertEqual(len(phone_matches), 0)


if __name__ == '__main__':
    unittest.main()
