import json
import unittest
from pathlib import Path

from april.config import Config
from april.errors import BackendError
from april.evaluate import evaluate_cases


class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_answered_does_not_mean_correct_and_failures_are_not_hidden(self):
        cases=json.loads((Path(__file__).resolve().parents[1]/'april/evaluation_cases.json').read_text())
        self.assertEqual(len({c['id'] for c in cases}),len(cases))
        class Backend:
            async def respond(self,text):return 'An intentionally wrong fixture answer'
        results=[r async for r in evaluate_cases(Backend(),Config(),cases[:1])]
        self.assertEqual(results[0]['status'],'answered')
        self.assertEqual(results[0]['review_status'],'unreviewed')
        self.assertNotIn('score',results[0])
        class Offline:
            async def respond(self,text):raise BackendError('ollama_unavailable','Not connected')
        failed=[r async for r in evaluate_cases(Offline(),Config(),cases)]
        self.assertEqual(len(failed),1) # No unchanged retries against an absent service.
        self.assertEqual(failed[0]['status'],'failed')
