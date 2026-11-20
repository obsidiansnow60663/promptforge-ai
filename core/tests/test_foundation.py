from unittest.mock import patch, MagicMock
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from core.models import CustomProvider, Prompt, Execution
from core.services import Provider, ProviderError, Response, generate, normalize_openai_endpoint

class FoundationTests(TestCase):
    def test_liveness(self):
        self.assertEqual(self.client.get(reverse('health')).json(), {'status': 'ok'})
        self.assertEqual(self.client.post(reverse('health')).status_code, 405)
    def test_home_does_not_require_login(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PromptForge')
    def test_login_routes_redirect_to_home(self):
        self.assertRedirects(self.client.get(reverse('login')), reverse('home'))
        self.assertRedirects(self.client.get(reverse('signup')), reverse('home'))

class EndpointNormalizationTests(SimpleTestCase):
    def test_normalize_openai_endpoint(self):
        self.assertEqual(
            normalize_openai_endpoint('http://localhost:11434'),
            'http://localhost:11434/v1/chat/completions'
        )
        self.assertEqual(
            normalize_openai_endpoint('http://localhost:11434/v1'),
            'http://localhost:11434/v1/chat/completions'
        )
        self.assertEqual(
            normalize_openai_endpoint('https://api.groq.com/openai/v1/chat/completions'),
            'https://api.groq.com/openai/v1/chat/completions'
        )
        self.assertEqual(
            normalize_openai_endpoint('localhost:8000/v1'),
            'http://localhost:8000/v1/chat/completions'
        )

class WorkflowTests(TestCase):
    def test_home(self):
        self.assertContains(self.client.get(reverse('home')), 'PromptForge')
    @patch('core.views.generate', return_value=({'primary_goal': 'test'}, 'English prompt', {'score': 90, 'revisions': 0}))
    @patch('core.views.Provider')
    def test_generate_saves_without_login(self, provider, generate_mock):
        response = self.client.post(reverse('run'), {'text': 'buat panduan', 'provider': 'openai', 'model': 'test', 'mode': 'generate'})
        self.assertContains(response, 'English prompt')
        prompt = Prompt.objects.get()
        self.assertIsNone(prompt.user)
        self.assertEqual(Execution.objects.count(), 0)
    @patch('core.views.execute', side_effect=ProviderError('provider gagal'))
    @patch('core.views.Provider')
    def test_execution_failure_is_saved(self, provider, execute_mock):
        response = self.client.post(reverse('run'), {'text': 'test', 'provider': 'openai', 'model': 'test', 'mode': 'execute'})
        self.assertContains(response, 'provider gagal')
        self.assertEqual(Execution.objects.get().status, 'failed')
    def test_public_access_to_prompt_detail_feedback_and_history(self):
        prompt = Prompt.objects.create(original='public prompt', provider='openai', model='x')
        detail_res = self.client.get(reverse('prompt_detail', args=[prompt.pk]))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, 'public prompt')
        fb_res = self.client.post(reverse('feedback', args=[prompt.pk]), {'rating': 5, 'comment': 'bagus'})
        self.assertEqual(fb_res.status_code, 302)
        self.assertEqual(prompt.feedback.count(), 1)
        history_res = self.client.get(reverse('history'))
        self.assertContains(history_res, 'public prompt')
    def test_invalid_mode_is_rejected(self):
        self.client.post(reverse('run'), {'text':'hello', 'provider':'openai', 'model':'test', 'mode':'unknown'})
        self.assertFalse(Prompt.objects.exists())

class CustomProviderTests(TestCase):
    def setUp(self):
        self.cp = CustomProvider.objects.create(
            name='Ollama Local',
            api_url='http://localhost:11434/v1',
            api_key='',
            default_model='llama3.2'
        )

    def test_custom_provider_page_and_creation(self):
        res = self.client.get(reverse('custom_providers'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Ollama Local')

        # Create new custom provider
        create_res = self.client.post(reverse('custom_providers'), {
            'name': 'Groq Cloud',
            'api_url': 'https://api.groq.com/openai/v1',
            'api_key': 'gsk_123',
            'default_model': 'llama-3.3-70b-versatile'
        })
        self.assertRedirects(create_res, reverse('custom_providers'))
        self.assertTrue(CustomProvider.objects.filter(name='Groq Cloud').exists())

    def test_custom_provider_delete(self):
        del_res = self.client.post(reverse('delete_custom_provider', args=[self.cp.pk]))
        self.assertRedirects(del_res, reverse('custom_providers'))
        self.assertFalse(CustomProvider.objects.filter(pk=self.cp.pk).exists())

    def test_provider_initialization_with_saved_custom_provider(self):
        provider = Provider(f'custom:{self.cp.id}', 'llama3.2')
        self.assertEqual(provider.name, f'custom:{self.cp.id}')
        self.assertEqual(provider.display_name, 'Ollama Local')
        self.assertEqual(provider.api_url, 'http://localhost:11434/v1')

    def test_provider_initialization_with_adhoc_custom_provider(self):
        provider = Provider('custom', 'mistral', api_url='http://localhost:8000/v1')
        self.assertEqual(provider.api_url, 'http://localhost:8000/v1')
        self.assertEqual(provider.model, 'mistral')

    @patch('core.views.generate', return_value=({'primary_goal': 'custom'}, 'Optimized with custom provider', {'score': 95, 'revisions': 0}))
    def test_run_with_custom_provider(self, generate_mock):
        res = self.client.post(reverse('run'), {
            'text': 'buat prompt kustom',
            'provider': f'custom:{self.cp.id}',
            'model': 'llama3.2',
            'mode': 'generate'
        })
        self.assertContains(res, 'Optimized with custom provider')
        prompt = Prompt.objects.get(original='buat prompt kustom')
        self.assertEqual(prompt.provider, 'Ollama Local')

    @patch('core.views.Provider.complete', return_value=Response('pong', {}))
    def test_test_custom_provider_endpoint(self, mock_complete):
        res = self.client.post(reverse('test_custom_provider'), {'provider_id': self.cp.id})
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('Respons diterima', data['message'])

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
    @patch('core.views.execute', return_value=('raw', 'hasil', {}, {'tokens': 2}, 15))
    @patch('core.views.Provider')
    def test_comparison_runs_same_prompt_and_saves_both_results(self, provider, execute_mock):
        response = self.client.post(reverse('compare'), {'text': 'same prompt', 'openai_model': 'one', 'google_model': 'two'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Execution.objects.filter(input_text='same prompt', status='completed').count(), 2)
        self.assertEqual(execute_mock.call_count, 2)
    @patch('core.views.generate', return_value=({}, 'prompt', {'critical_failure': True, 'warning': True, 'score': 99, 'revisions': 2}))
    @patch('core.views.execute')
    @patch('core.views.Provider')
    def test_quality_gate_stops_automatic_execution(self, provider, execute_mock, generate_mock):
        response = self.client.post(reverse('run'), {'text': 'test', 'provider': 'openai', 'model': 'test', 'mode': 'generate_execute'})
        self.assertContains(response, 'Eksekusi dihentikan')
        execute_mock.assert_not_called()
