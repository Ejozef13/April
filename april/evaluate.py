"""Text-only local-model evaluation with explicit retention and human review.

This isolates model output from STT/TTS. Fixture tests validate this runner;
they do not establish the actual model's accuracy. Never emit reasoning.
"""
import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .backends import LocalBackends
from .config import load_config
from .errors import BackendError


async def evaluate_cases(backend, config, cases):
    for case in cases:
        started = time.perf_counter()
        record = {'type': 'result', 'case_id': case['id'], 'category': case['category'],
                  'question': case['question'], 'rubric': case['rubric'],
                  'reference': case['reference'], 'review_status': 'unreviewed'}
        try:
            async with asyncio.timeout(config.timeout_seconds):
                answer = await backend.respond(case['question'])
            if not isinstance(answer, str) or not answer.strip():
                raise BackendError('empty_answer', 'No final answer was returned.')
            record.update(status='answered', answer=answer[:config.max_response_chars])
        except BackendError as exc:
            record.update(status='failed', error_code=exc.code, message=str(exc))
        except TimeoutError:
            record.update(status='failed', error_code='deadline', message='The configured request deadline expired.')
        except Exception:
            record.update(status='failed', error_code='unexpected_backend_failure', message='Backend failed; no raw diagnostic body retained.')
        record['request_ms'] = round((time.perf_counter() - started) * 1000, 1)
        yield record
        # Repeated requests cannot fix an absent service or rejected model.
        if record.get('error_code') in {'ollama_unavailable', 'ollama_request_failed'}:
            return


def main():
    parser = argparse.ArgumentParser(description='Save a text-only baseline for manual review; no automatic accuracy score.')
    parser.add_argument('--output', required=True, type=Path, help='New local JSONL report; existing files are never overwritten')
    args = parser.parse_args()
    try:
        config = load_config()
    except (ValueError, TypeError, OSError, KeyError):
        parser.exit(1, 'Check april.local.toml before evaluating.\n')
    if config.mode != 'live':
        parser.exit(1, 'Evaluation requires live mode. Simulation cannot measure model accuracy.\n')
    cases = json.loads(Path(__file__).with_name('evaluation_cases.json').read_text())
    metadata = {'type':'run', 'schema_version':1, 'started_at':datetime.now(timezone.utc).isoformat(),
                'mode':'live', 'model':config.model, 'reasoning_effort':config.reasoning_effort,
                'context_tokens':config.context_tokens, 'max_response_tokens':config.max_response_tokens,
                'max_response_chars':config.max_response_chars, 'planned_cases':len(cases),
                'condition':'unknown', 'audio_included':False, 'reasoning_included':False,
                'scope':'Single-turn text through APRIL adapter; includes connection/generation and any loading, excludes STT/TTS/playback.',
                'accuracy_status':'unreviewed; model completion is not a correctness grade'}
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report = args.output.open('x')
    except OSError:
        parser.exit(1, 'Cannot create report. Choose a new writable output path; existing reports are preserved.\n')
    print('Stop APRIL voice requests during this run; leave shared AM/Ollama services intact.')
    print('Saving public test questions and final answers locally. Review before sharing.')

    async def run():
        failed = 0
        completed = 0
        with report:
            report.write(json.dumps(metadata) + '\n')
            report.flush()
            async for record in evaluate_cases(LocalBackends(config), config, cases):
                completed += 1
                failed += record['status'] == 'failed'
                report.write(json.dumps(record, ensure_ascii=False) + '\n')
                report.flush()
                print(f"{record['case_id']}: {record['status']} (accuracy unreviewed)", flush=True)
            report.write(json.dumps({'type':'summary', 'attempted':completed,
                'backend_failures':failed, 'not_run':len(cases)-completed,
                'correctness_reviewed':0}) + '\n')
        return failed

    try:
        failures = asyncio.run(run())
    except KeyboardInterrupt:
        parser.exit(130, 'Interrupted. Completed records remain in the partial report; there is no complete-run summary.\n')
    print(f'Report saved to {args.output}. Read the answers against the rubrics; no accuracy score has been assigned.')
    if failures:
        parser.exit(1, 'One or more backend requests failed; failed/unrun cases are not passing results.\n')


if __name__ == '__main__':
    main()
