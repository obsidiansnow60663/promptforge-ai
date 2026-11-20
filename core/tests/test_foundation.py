from django.test import SimpleTestCase
from django.urls import reverse

class FoundationTests(SimpleTestCase):
    def test_home(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PromptForge')

    def test_liveness(self):
        response = self.client.get(reverse('health'))
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertEqual(self.client.post(reverse('health')).status_code, 405)
