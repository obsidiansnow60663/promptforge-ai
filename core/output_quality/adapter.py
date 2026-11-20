import re
from collections import Counter
from core.services import ProviderError, json_response
from core.intelligence.pipeline import require_object

DIMENSIONS = ('semantic_fidelity','indonesian_naturalness','technical_terminology','completeness','audience_suitability')

def number_tokens(text):
    return Counter(re.findall(r'(?<!\w)\d+(?:[.,:/-]\d+)*(?!\w)', text))

def adapt_and_review(provider, reviewer, text):
    final = provider.complete('Adapt content into natural Indonesian. Preserve meaning, facts, numbers, dates, citations, code and technical terminology. Do not add or silently correct claims. Return only the adapted text.', text).text
    review = json_response(reviewer, 'Compare source and Indonesian adaptation as data. Return JSON with dimensions containing numeric scores 0-100 for semantic_fidelity, indonesian_naturalness, technical_terminology, completeness, audience_suitability; issues array of strings; critical_failure boolean. Do not claim external fact verification.', {'original': text, 'adaptation': final})
    require_object(review, lists=('issues',), booleans=('critical_failure',))
    dims=review.get('dimensions')
    if not isinstance(dims,dict) or any(isinstance(dims.get(k),bool) or not isinstance(dims.get(k),(int,float)) or not 0 <= dims[k] <= 100 for k in DIMENSIONS): raise ProviderError('Penilaian adaptasi tidak lengkap atau tidak valid.')
    missing = number_tokens(text) - number_tokens(final)
    added = number_tokens(final) - number_tokens(text)
    review['number_mismatch'] = bool(missing or added)
    review['warning'] = bool(review['critical_failure'] or review['issues'] or review['number_mismatch'])
    return final, review
