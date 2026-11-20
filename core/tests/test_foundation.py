from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from core.models import Prompt, Execution
from core.services import ProviderError, Response, generate

class FoundationTests(SimpleTestCase):
    def test_liveness(self):
        self.assertEqual(self.client.get(reverse('health')).json(), {'status': 'ok'})
        self.assertEqual(self.client.post(reverse('health')).status_code, 405)
    def test_home_requires_login(self):
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)

class WorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tester', password='Testpass123!')
        self.other = User.objects.create_user('other', password='Testpass123!')
        self.client.force_login(self.user)
    def test_home(self):
        self.assertContains(self.client.get(reverse('home')), 'PromptForge')
    @patch('core.views.generate', return_value=({'primary_goal': 'test'}, 'English prompt', {'score': 90, 'revisions': 0}))
    @patch('core.views.Provider')
    def test_generate_saves_for_user(self, provider, generate_mock):
        response = self.client.post(reverse('run'), {'text': 'buat panduan', 'provider': 'openai', 'model': 'test', 'mode': 'generate'})
        self.assertContains(response, 'English prompt')
        self.assertEqual(Prompt.objects.get().user, self.user)
        self.assertEqual(Execution.objects.count(), 0)
    @patch('core.views.execute', side_effect=ProviderError('provider gagal'))
    @patch('core.views.Provider')
    def test_execution_failure_is_saved(self, provider, execute_mock):
        response = self.client.post(reverse('run'), {'text': 'test', 'provider': 'openai', 'model': 'test', 'mode': 'execute'})
        self.assertContains(response, 'provider gagal')
        self.assertEqual(Execution.objects.get().status, 'failed')
    def test_other_users_cannot_access_prompt_or_submit_feedback(self):
        prompt = Prompt.objects.create(user=self.other, original='private', provider='openai', model='x')
        self.assertEqual(self.client.get(reverse('prompt_detail', args=[prompt.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('feedback', args=[prompt.pk]), {'rating': 5}).status_code, 404)
        self.assertNotContains(self.client.get(reverse('history')), 'private')
    def test_invalid_mode_is_rejected(self):
        self.client.post(reverse('run'), {'text':'hello', 'provider':'openai', 'model':'test', 'mode':'unknown'})
        self.assertFalse(Prompt.objects.exists())

class ReviewLoopTests(SimpleTestCase):
    def test_critical_failure_triggers_at_most_two_revisions(self):
        import json
        from core.services import WEIGHTS
        class FakeProvider:
            def __init__(self): self.calls = 0
            def complete(self, system, user, **kwargs):
                self.calls += 1
                if 'Analyze the user input' in system: return Response(json.dumps({'primary_goal':'test', 'input_language':'id', 'output_language':'id', 'constraints':[], 'expected_output':[], 'ambiguities':[]}), {})
                if 'Extract context' in system: return Response(json.dumps({'domain':'test','audience':'unspecified','facts':[],'constraints':[]}), {})
                if 'Design a prompt structure' in system: return Response(json.dumps({'objective':'test','sections':[],'constraints':[],'output_requirements':[]}), {})
                if 'Review the prompt' in system: return Response(json.dumps({'dimensions': {k: 100 for k in WEIGHTS}, 'critical_failure': True, 'missing':['constraint'], 'unsupported_assumptions':[], 'ambiguities':[]}), {})
                return Response('draft', {})
        p = FakeProvider()
        _, _, review = generate(p, 'test')
        self.assertTrue(review['warning'])
        self.assertEqual(review['revisions'], 2)
        self.assertEqual(p.calls, 9)

class ComparisonTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('compare', password='Testpass123!')
        self.client.force_login(self.user)
    @patch('core.views.execute', return_value=('raw', 'hasil', {}, {'tokens': 2}, 15))
    @patch('core.views.Provider')
    def test_comparison_runs_same_prompt_and_saves_both_results(self, provider, execute_mock):
        response = self.client.post(reverse('compare'), {'text': 'same prompt', 'openai_model': 'one', 'google_model': 'two'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Execution.objects.filter(user=self.user, input_text='same prompt', status='completed').count(), 2)
        self.assertEqual(execute_mock.call_count, 2)
    @patch('core.views.generate', return_value=({}, 'prompt', {'critical_failure': True, 'warning': True, 'score': 99, 'revisions': 2}))
    @patch('core.views.execute')
    @patch('core.views.Provider')
    def test_quality_gate_stops_automatic_execution(self, provider, execute_mock, generate_mock):
        response = self.client.post(reverse('run'), {'text': 'test', 'provider': 'openai', 'model': 'test', 'mode': 'generate_execute'})
        self.assertContains(response, 'Eksekusi dihentikan')
        execute_mock.assert_not_called()
