from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from core.intelligence.pipeline import ClarificationRequired, require_object, review_prompt
from core.output_quality.adapter import number_tokens, adapt_and_review
from core.services import ProviderError, Response, WEIGHTS

class QualityValidationTests(SimpleTestCase):
    def test_required_lists_cannot_be_missing_or_wrong_type(self):
        for value in ({}, {'missing': 'none'}, {'missing': [4]}):
            with self.assertRaises(ProviderError): require_object(value, lists=('missing',))
    @patch('core.intelligence.pipeline.json_response')
    def test_review_rejects_missing_list_even_if_score_is_high(self, result):
        result.return_value = {'dimensions': {k: 100 for k in WEIGHTS}, 'critical_failure': False, 'unsupported_assumptions': [], 'ambiguities': []}
        with self.assertRaises(ProviderError): review_prompt(None, 'source', 'prompt', {}, {})
    def test_number_check_detects_changes(self):
        self.assertNotEqual(number_tokens('On 2025-01-02: 42'), number_tokens('Pada 2025-01-02: 43'))
    @patch('core.output_quality.adapter.json_response')
    def test_changed_number_triggers_warning(self, review):
        from core.output_quality.adapter import DIMENSIONS
        review.return_value = {'dimensions': {k: 100 for k in DIMENSIONS}, 'issues': [], 'critical_failure': False}
        class Provider:
            def complete(self, *args): return Response('Hasil 41', {})
        _, result = adapt_and_review(Provider(), Provider(), 'Result 42')
        self.assertTrue(result['number_mismatch'])
        self.assertTrue(result['warning'])

class ClarificationFlowTests(TestCase):
    def setUp(self):
        user = User.objects.create_user('clarify', password='Testpass123!'); self.client.force_login(user)
    @patch('core.views.Provider')
    @patch('core.views.generate')
    def test_clarification_resumes_with_original_and_answer(self, generate, provider):
        generate.side_effect = [ClarificationRequired(['Siapa audiensnya?']), ({}, 'prompt', {'warning':False,'score':90,'revisions':0})]
        first=self.client.post(reverse('run'), {'text':'buat panduan','provider':'openai','model':'test','mode':'generate'})
        self.assertContains(first, 'Siapa audiensnya?')
        second=self.client.post(reverse('run'), {'mode':'clarify','clarification':'Untuk pemula'})
        self.assertContains(second, 'prompt')
        self.assertEqual(generate.call_args.args[1], 'buat panduan')
        self.assertEqual(generate.call_args.args[4], 'Untuk pemula')
