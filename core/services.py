"""Provider boundary and independent intelligence, execution, and localization stages."""
import json
import logging
import os
import time
from dataclasses import dataclass
from urllib import error, request

logger = logging.getLogger(__name__)
PROVIDERS = {
    'openai': ('OPENAI_API_KEY', 'gpt-4o-mini'),
    'anthropic': ('ANTHROPIC_API_KEY', 'claude-3-5-haiku-latest'),
    'google': ('GOOGLE_API_KEY', 'gemini-2.0-flash'),
}
WEIGHTS = {
    'intent_preservation': 25,
    'requirement_completeness': 25,
    'clarity': 15,
    'technical_precision': 15,
    'output_alignment': 10,
    'factual_integrity': 10,
}

class ProviderError(Exception):
    pass

@dataclass
class Response:
    text: str
    usage: dict

def normalize_openai_endpoint(url: str) -> str:
    url = (url or '').strip()
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    url = url.rstrip('/')
    if url.endswith('/chat/completions'):
        return url
    if url.endswith('/v1'):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"

class Provider:
    def __init__(self, name, model, api_url=None, api_key=None, display_name=None):
        if not name or len(name) > 64 or not model or len(model) > 120:
            raise ProviderError('Provider atau model tidak valid.')
        self.name = name
        self.model = model
        self.display_name = display_name or name
        self.api_url = api_url
        self.key = api_key or ''

        if name in PROVIDERS:
            if not self.key:
                self.key = os.getenv(PROVIDERS[name][0], '')
            if not self.key:
                raise ProviderError(f'API key {name} belum dikonfigurasi di server.')
            self.display_name = name.title()
        else:
            if not self.api_url:
                from .models import CustomProvider
                cp = None
                if name.startswith('custom:'):
                    cp_id = name.split(':', 1)[1]
                    if cp_id.isdigit():
                        cp = CustomProvider.objects.filter(id=int(cp_id), is_active=True).first()
                if not cp:
                    cp = CustomProvider.objects.filter(name=name, is_active=True).first()
                if cp:
                    self.api_url = cp.api_url
                    if not self.key and cp.api_key:
                        self.key = cp.api_key
                    self.display_name = cp.name
                else:
                    raise ProviderError(f'Konfigurasi provider kustom "{name}" tidak ditemukan.')

            if not self.api_url:
                raise ProviderError('URL endpoint untuk provider kustom harus diisi.')

    def complete(self, system, user, temperature=0.2):
        if self.name == 'anthropic':
            url = 'https://api.anthropic.com/v1/messages'
            headers = {'x-api-key': self.key, 'anthropic-version': '2023-06-01'}
            body = {'model': self.model, 'system': system, 'messages': [{'role': 'user', 'content': user}], 'max_tokens': 4096, 'temperature': temperature}
        elif self.name == 'google':
            from urllib.parse import quote
            url = 'https://generativelanguage.googleapis.com/v1beta/models/' + quote(self.model, safe='') + ':generateContent'
            headers = {'x-goog-api-key': self.key}
            body = {'systemInstruction': {'parts': [{'text': system}]}, 'contents': [{'role': 'user', 'parts': [{'text': user}]}], 'generationConfig': {'temperature': temperature}}
        elif self.name == 'openai':
            url = self.api_url or 'https://api.openai.com/v1/chat/completions'
            headers = {'Authorization': f'Bearer {self.key}'}
            body = {'model': self.model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'temperature': temperature}
        else:
            url = normalize_openai_endpoint(self.api_url)
            headers = {}
            if self.key:
                headers['Authorization'] = f'Bearer {self.key}'
            body = {'model': self.model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'temperature': temperature}

        headers['Content-Type'] = 'application/json'
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        req = request.Request(url, data=json.dumps(body).encode(), headers=headers, method='POST')
        for attempt in range(3):
            try:
                with request.urlopen(req, timeout=60) as resp:
                    data = json.load(resp)
                if self.name == 'anthropic':
                    result = '\n'.join(x.get('text', '') for x in data.get('content', []) if x.get('type') == 'text')
                    usage = data.get('usage', {})
                elif self.name == 'google':
                    result = '\n'.join(x.get('text', '') for x in data['candidates'][0]['content']['parts'])
                    usage = data.get('usageMetadata', {})
                else:
                    choices = data.get('choices', [])
                    if not choices:
                        raise ValueError('Respons provider tidak memiliki pilihan jawaban (choices).')
                    result = choices[0].get('message', {}).get('content', '')
                    usage = data.get('usage', {})
                if not result:
                    raise ValueError('empty response')
                return Response(result, usage)
            except error.HTTPError as exc:
                if (exc.code == 429 or 500 <= exc.code < 600) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                logger.warning('Provider request failed: provider=%s status=%s', self.name, exc.code)
                display = getattr(self, 'display_name', self.name)
                raise ProviderError(f'Provider {display} menolak permintaan (HTTP {exc.code}). Periksa konfigurasi dan kuota.') from exc
            except (error.URLError, TimeoutError) as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                display = getattr(self, 'display_name', self.name)
                raise ProviderError(f'Provider {display} tidak dapat dihubungi atau waktu habis.') from exc
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                display = getattr(self, 'display_name', self.name)
                raise ProviderError(f'Format respons {display} tidak valid.') from exc

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
