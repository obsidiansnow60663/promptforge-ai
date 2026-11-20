from django.conf import settings
from django.db import models

class CustomProvider(models.Model):
    name = models.CharField(max_length=64, unique=True)
    api_url = models.CharField(max_length=500, help_text="Base URL atau endpoint OpenAI-compatible (misal: http://localhost:11434/v1 atau https://api.groq.com/openai/v1)")
    api_key = models.CharField(max_length=255, blank=True, help_text="API Key (opsional jika provider lokal)")
    default_model = models.CharField(max_length=120, default='gpt-4o-mini')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Prompt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='prompts')
    original = models.TextField()
    optimized = models.TextField(blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    review = models.JSONField(default=dict, blank=True)
    provider = models.CharField(max_length=64)
    model = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class Execution(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='executions')
    prompt = models.ForeignKey(Prompt, on_delete=models.SET_NULL, null=True, blank=True, related_name='executions')
    input_text = models.TextField()
    provider = models.CharField(max_length=64)
    model = models.CharField(max_length=120)
    status = models.CharField(max_length=20, default='pending')
    raw_output = models.TextField(blank=True)
    final_output = models.TextField(blank=True)
    output_review = models.JSONField(default=dict, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE, related_name='feedback')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
