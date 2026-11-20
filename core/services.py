"""Provider boundary and independent intelligence, execution, and localization stages."""
import json
import logging
import os
import time
from dataclasses import dataclass
from urllib import error, request

logger = logging.getLogger(__name__)
PROVIDERS = {'openai': ('OPENAI_API_KEY', 'gpt-4o-mini'), 'anthropic': ('ANTHROPIC_API_KEY', 'claude-3-5-haiku-latest'), 'google': ('GOOGLE_API_KEY', 'gemini-2.0-flash')}
WEIGHTS = {'intent_preservation': 25, 'requirement_completeness': 25, 'clarity': 15, 'technical_precision': 15, 'output_alignment': 10, 'factual_integrity': 10}

class ProviderError(Exception):
    pass

@dataclass
class Response:
    text: str
    usage: dict

class Provider:
    def __init__(self, name, model):
        if name not in PROVIDERS or not model or len(model) > 120:
            raise ProviderError('Provider atau model tidak valid.')
        self.name, self.model = name, model
        self.key = os.getenv(PROVIDERS[name][0], '')
        if not self.key:
            raise ProviderError(f'API key {name} belum dikonfigurasi di server.')

    def complete(self, system, user, temperature=0.2):
        if self.name == 'openai':
            url = 'https://api.openai.com/v1/chat/completions'
            headers = {'Authorization': f'Bearer {self.key}'}
            body = {'model': self.model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'temperature': temperature}
        elif self.name == 'anthropic':
            url = 'https://api.anthropic.com/v1/messages'
            headers = {'x-api-key': self.key, 'anthropic-version': '2023-06-01'}
            body = {'model': self.model, 'system': system, 'messages': [{'role': 'user', 'content': user}], 'max_tokens': 4096, 'temperature': temperature}
        else:
            from urllib.parse import quote
            url = 'https://generativelanguage.googleapis.com/v1beta/models/' + quote(self.model, safe='') + ':generateContent'
            headers = {'x-goog-api-key': self.key}
            body = {'systemInstruction': {'parts': [{'text': system}]}, 'contents': [{'role': 'user', 'parts': [{'text': user}]}], 'generationConfig': {'temperature': temperature}}
        headers['Content-Type'] = 'application/json'
        req = request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')
        for attempt in range(3):
            try:
                with request.urlopen(req, timeout=60) as resp:
                    data = json.load(resp)
                if self.name == 'openai':
                    result = data['choices'][0]['message']['content']; usage = data.get('usage', {})
                elif self.name == 'anthropic':
                    result = '\n'.join(x.get('text', '') for x in data['content'] if x.get('type') == 'text'); usage = data.get('usage', {})
                else:
                    result = '\n'.join(x.get('text', '') for x in data['candidates'][0]['content']['parts']); usage = data.get('usageMetadata', {})
                if not result: raise ValueError('empty response')
                return Response(result, usage)
            except error.HTTPError as exc:
                if (exc.code == 429 or 500 <= exc.code < 600) and attempt < 2:
                    time.sleep(2 ** attempt); continue
                logger.warning('Provider request failed: provider=%s status=%s', self.name, exc.code)
                raise ProviderError(f'Provider {self.name} menolak permintaan (HTTP {exc.code}). Periksa konfigurasi dan kuota.') from exc
            except (error.URLError, TimeoutError) as exc:
                if attempt < 2: time.sleep(2 ** attempt); continue
                raise ProviderError(f'Provider {self.name} tidak dapat dihubungi atau waktu habis.') from exc
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                raise ProviderError(f'Format respons {self.name} tidak valid.') from exc

def json_response(provider, system, payload):
    raw = provider.complete(system + '\nReturn only a valid JSON object without markdown.', json.dumps(payload, ensure_ascii=False)).text.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0]
    try:
        value = json.loads(raw)
        if not isinstance(value, dict): raise ValueError()
        return value
    except ValueError as exc:
        raise ProviderError('Respons terstruktur AI tidak valid; coba lagi.') from exc

def generate(provider, original, instructions='', reviewer=None, clarification=''):
    from core.intelligence.pipeline import generate as run_pipeline
    return run_pipeline(provider, original, instructions, reviewer, clarification)

def execute(provider, prompt, adapt=True, reviewer=None):
    from core.output_quality.adapter import adapt_and_review
    start = time.monotonic()
    response = provider.complete('Execute the user prompt. Follow its requested output language and format.', prompt)
    final, review = response.text, {}
    if adapt:
        final, review = adapt_and_review(provider, reviewer or provider, response.text)
    return response.text, final, review, response.usage, int((time.monotonic() - start) * 1000)
