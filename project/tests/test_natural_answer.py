"""Mocked Solar chat checks; no company documents or live API calls."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / '.packages'))
sys.path.insert(0, str(ROOT / 'backend'))

import httpx
from natural_answer import answer_with_api
from user_agent import AgentError


def quote(identifier, name):
    return {'id': identifier, 'project_name': name, 'customer': '가상 고객',
            'source_text': '전송하면 안 되는 원문', 'source_url': '/api/files/private.pdf',
            'updated_at': '2026-10-14', 'items': [
                {'name': '브라켓', 'unit_price': 12000, 'amount': None,
                 'option_group': 'A 또는 B 중 선택'}]}


class NaturalAnswerTests(unittest.TestCase):
    def test_question_uses_only_saved_fields_and_request_key(self):
        seen = []
        def handle(request):
            self.assertEqual(str(request.url), 'https://api.upstage.ai/v1/chat/completions')
            self.assertEqual(request.headers['Authorization'], 'Bearer FAKE_USER_KEY')
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'solar-pro4')
            self.assertIn('Markdown 파이프 표', body['messages'][0]['content'])
            prompt = json.loads(body['messages'][1]['content'])
            self.assertEqual(prompt['previous_turns'], [{'role': 'user', 'content': '앞 질문'},
                                                         {'role': 'assistant', 'content': '앞 답변'}])
            self.assertNotIn('전송하면 안 되는 원문', request.content.decode())
            self.assertNotIn('private.pdf', request.content.decode())
            self.assertIn('A 또는 B 중 선택', request.content.decode())
            seen.append(body)
            return httpx.Response(200, json={'choices': [{'message': {'content':
                '브라켓 단가는 12,000원으로 저장되어 있습니다 [1].'}}],
                'usage': {'prompt_tokens': 120, 'completion_tokens': 20, 'total_tokens': 140}})
        result = answer_with_api('브라켓 단가는?', [quote('test-1', '가상 견적')],
                                 'FAKE_USER_KEY', httpx.MockTransport(handle),
                                 history=[{'role': 'user', 'content': '앞 질문'},
                                          {'role': 'assistant', 'content': '앞 답변'}])
        self.assertEqual(len(seen), 1)
        self.assertEqual(result['method'], 'upstage-solar')
        self.assertEqual(result['quotes'][0]['id'], 'test-1')
        self.assertIn('[1]', result['answer'])
        self.assertEqual(result['model'], 'solar-pro4')
        self.assertEqual(result['usage'], {'prompt_tokens': 120, 'completion_tokens': 20, 'total_tokens': 140})

    def test_mini_model_and_unreported_usage(self):
        def handle(request):
            self.assertEqual(json.loads(request.content)['model'], 'solar-mini4')
            return httpx.Response(200, json={'choices': [{'message': {'content': '가상 답변 [1]'}}]})
        result = answer_with_api('질문', [quote('test-1', '가상 견적')], 'FAKE_USER_KEY',
                                 httpx.MockTransport(handle), model='solar-mini4')
        self.assertEqual(result['model'], 'solar-mini4')
        self.assertIsNone(result['usage'])
        with self.assertRaises(AgentError):
            answer_with_api('질문', [quote('test-1', '가상 견적')], 'FAKE_USER_KEY',
                            httpx.MockTransport(handle), model='other-model')

    def test_no_documents_skips_api(self):
        result = answer_with_api('뭐가 있어?', [], 'FAKE_USER_KEY')
        self.assertEqual(result['method'], 'no-documents')

    def test_partial_scope_and_safe_provider_errors(self):
        rows = [quote(f'test-{index}', f'가상 견적 {index}') for index in range(22)]
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            'choices': [{'message': {'content': '제공된 문서만 확인했습니다.'}}]}))
        result = answer_with_api('가상 견적 알려줘', rows, 'FAKE_USER_KEY', transport)
        self.assertEqual(len(result['quotes']), 20)
        self.assertIn('일부 문서', result['scope_note'])
        failed = httpx.MockTransport(lambda request: httpx.Response(401, json={
            'error': 'FAKE_USER_KEY'}))
        with self.assertRaises(AgentError) as error:
            answer_with_api('질문', rows[:1], 'FAKE_USER_KEY', failed)
        self.assertNotIn('FAKE_USER_KEY', str(error.exception))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(NaturalAnswerTests))
    (ROOT / 'tests' / 'natural-answer-results.json').write_text(json.dumps({
        'ok': result.wasSuccessful(), 'tests_run': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors),
        'live_api_called': False
    }, indent=2), encoding='utf-8')
    sys.exit(not result.wasSuccessful())
