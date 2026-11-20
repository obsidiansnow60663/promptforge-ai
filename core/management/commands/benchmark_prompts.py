import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from core.intelligence.pipeline import ClarificationRequired
from core.services import Provider, ProviderError, generate

class Command(BaseCommand):
    help = 'Run three prompt baselines using one execution model. Results require human evaluation and incur API costs.'
    def add_arguments(self, parser):
        parser.add_argument('--dataset', required=True)
        parser.add_argument('--output', required=True)
        parser.add_argument('--provider', required=True)
        parser.add_argument('--model', required=True)
    def handle(self, *args, **opts):
        try:
            samples = json.loads(Path(opts['dataset']).read_text(encoding='utf8'))
            if not isinstance(samples, list) or not samples: raise ValueError('dataset must be a nonempty list')
            fields = ('id','category','original','expected_intent','mandatory_constraints','expected_output_format','output_language','criteria')
            for sample in samples:
                if not isinstance(sample, dict) or any(k not in sample for k in fields) or not isinstance(sample['mandatory_constraints'], list): raise ValueError('missing required dataset fields')
            provider = Provider(opts['provider'], opts['model'])
        except (OSError, ValueError, ProviderError) as exc:
            raise CommandError(str(exc)) from exc
        reports=[]
        for sample in samples:
            row={'id':sample['id'],'category':sample['category'],'criteria':sample['criteria'],'expected_intent':sample['expected_intent'],'mandatory_constraints':sample['mandatory_constraints'],'conditions':{}}
            try:
                literal=provider.complete('Translate the following text literally to English, retaining all meaning, output language and constraints. Return only the translation.', sample['original']).text
                _, optimized, review=generate(provider,sample['original'])
                variants={'original':sample['original'],'literal':literal,'optimized':optimized}
                if review['warning']: row['warning']='Optimized prompt failed quality gate; review before comparing.'
                for name, prompt in variants.items():
                    answer=provider.complete('Execute the user prompt. Follow its requested output language and format.',prompt)
                    row['conditions'][name]={'prompt':prompt,'output':answer.text,'usage':answer.usage,'human_rating':None,'human_notes':''}
            except (ProviderError, ClarificationRequired) as exc:
                row['error']=str(exc)
                if isinstance(exc, ClarificationRequired): row['questions']=exc.questions
            reports.append(row)
        try: Path(opts['output']).write_text(json.dumps({'provider':opts['provider'],'model':opts['model'],'results':reports},ensure_ascii=False,indent=2),encoding='utf8')
        except OSError as exc: raise CommandError(str(exc)) from exc
        self.stdout.write(f'Saved {len(reports)} cases to {opts["output"]}; human assessment is required.')
