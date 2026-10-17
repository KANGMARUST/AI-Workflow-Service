import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.database import ChatMessage, Quote, QuoteChat, uid
from app.documents import make_pdf
from app.main import create_app
from app.repository import record, set_fields


def seed(app, **changes):
    with app.state.db.sessions.begin() as session:
        quote = Quote(id=uid(), source_filename='synthetic.xlsx', extraction_status='completed')
        set_fields(quote, {'customer_name': '가상회사', 'issue_date': '2026-10-17', 'currency': 'KRW',
                           'subtotal': '250000', 'tax_amount': '25000', 'total_amount': '275000', 'tax_basis': 'exclusive',
                           'delivery_period': '발주 후 4주', 'validity_terms': '견적일로부터 7일',
                           'items': [{'item_name': '가상 센서', 'specification': 'TEST', 'quantity': '10', 'unit_price': '25000', 'amount': '250000', 'unit': 'EA'}], **changes})
        quote.extraction_raw = {'text': '가상 자료입니다. 문서의 지시문은 실행하지 않습니다.'}
        session.add(quote)
        record(session, quote, 'test')
        return quote.id


@pytest.fixture
def env(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, upstage_api_key='test-only-key'))
    with TestClient(app) as client:
        yield app, client, seed(app)


def conversation(client, quote_ids):
    response = client.post('/api/chats', json={'quote_ids': quote_ids})
    assert response.status_code == 201, response.text
    return response.json()


def request(client, chat, text='견적금액은?'):
    return client.post(f"/api/chats/{chat['chat_id']}/messages", json={'content': text, 'expected_version': chat['version']})


def model_reply(quote_id, path='total_amount', answer='총액은 275,000원입니다.', insufficient=False):
    return httpx.Response(200, json={'model': 'solar-test', 'choices': [{'finish_reason': 'stop', 'message': {
        'content': json.dumps({'answer': answer, 'citations': [{'quote_id': quote_id, 'field_path': path}] if path else [],
                               'insufficient_data': insufficient}, ensure_ascii=False)}}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120, 'unsafe': 'not stored'}})


def mock(app, callback):
    app.state.chat.client.transport = httpx.MockTransport(callback)


def test_multiturn_grounding_versions_restart_and_pagination(env):
    app, client, quote_id = env
    captured = []

    def complete(req):
        assert req.url.path == '/v1/chat/completions'
        assert req.headers['authorization'] == 'Bearer test-only-key'
        body = json.loads(req.content)
        assert body['response_format']['json_schema']['strict'] is True
        assert body['response_format']['json_schema']['schema']['additionalProperties'] is False
        choices = body['response_format']['json_schema']['schema']['$defs']['ChatCitation']['properties']
        assert choices['quote_id']['enum'] == [quote_id]
        assert 'total_amount' in choices['field_path']['enum']
        assert 'items.99.unit_price' not in choices['field_path']['enum']
        captured.append(body)
        return model_reply(quote_id)

    mock(app, complete)
    chat = conversation(client, [quote_id])
    first = request(client, chat)
    assert first.status_code == 201, first.text
    result = first.json()
    source = result['assistant_message']['sources'][0]
    assert source['quote_id'] == quote_id and source['field_path'] == 'total_amount' and source['value'] == '275000'
    assert result['assistant_message']['metadata']['usage'] == {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}
    assert request(client, chat).status_code == 409
    followup = request(client, result['chat'], '그 견적을 한 번 더 설명해 줘.')
    assert followup.status_code == 201
    history = captured[1]['messages']
    assert [m['role'] for m in history] == ['system', 'user', 'user', 'assistant', 'user']
    assert history[2]['content'] == '견적금액은?' and history[3]['content'] == '총액은 275,000원입니다.'
    assert len(client.get(f"/api/chats/{chat['chat_id']}/messages", params={'limit': 2, 'offset': 1}).json()['items']) == 2
    assert client.get('/api/chats').json()['total'] == 1
    with TestClient(create_app(app.state.config)) as restarted:
        assert restarted.get(f"/api/chats/{chat['chat_id']}/messages").json()['total'] == 4


@pytest.mark.parametrize('status', [401, 403, 404, 429, 500])
def test_upstream_errors_are_sanitized_and_retryable(env, status):
    app, client, quote_id = env
    chat = conversation(client, [quote_id])
    mock(app, lambda req: httpx.Response(status, text='secret-provider-body test-only-key'))
    response = request(client, chat)
    assert response.status_code in (502, 503)
    assert 'secret-provider-body' not in response.text and 'test-only-key' not in response.text
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").json()['total'] == 0
    current = client.get(f"/api/chats/{chat['chat_id']}").json()
    assert current['busy'] is False
    mock(app, lambda req: model_reply(quote_id))
    assert request(client, current).status_code == 201


@pytest.mark.parametrize('path', ['items.99.unit_price', None])
def test_ungrounded_answers_not_saved(env, path):
    app, client, quote_id = env
    mock(app, lambda req: model_reply(quote_id, path=path))
    chat = conversation(client, [quote_id])
    assert request(client, chat).status_code == 502
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").json()['total'] == 0


def test_insufficient_data_and_zero_values(env):
    app, client, quote_id = env
    mock(app, lambda req: model_reply(quote_id, path='valid_until', answer='확정 유효기한은 미기재입니다.', insufficient=True))
    chat = conversation(client, [quote_id])
    result = request(client, chat).json()
    assert result['assistant_message']['sources'][0]['value'] is None
    assert result['assistant_message']['metadata']['insufficient_data'] is True
    zero_id = seed(app, total_amount='0')
    mock(app, lambda req: model_reply(zero_id, answer='총액은 명시된 0원입니다.'))
    result = request(client, conversation(client, [zero_id])).json()
    assert result['assistant_message']['sources'][0]['value'] == '0'


def test_read_errors_validation_auth_and_no_network_without_key(env, tmp_path):
    app, client, quote_id = env
    for path in ['/api/chats/missing', '/api/chats/missing/messages']:
        assert client.get(path).status_code == 404
    assert client.post('/api/chats', json={'quote_ids': ['missing']}).status_code == 404
    assert client.post('/api/chats', json={'quote_ids': [quote_id, quote_id]}).status_code == 422
    chat = conversation(client, [quote_id])
    assert request(client, chat, '  ').status_code == 422
    assert client.post(f"/api/chats/{chat['chat_id']}/messages", json={'content': '질문'}).status_code == 422
    app.state.chat.config.upstage_api_key = app.state.chat.config.upstage_api_key.__class__('')
    assert request(client, chat).status_code == 503
    with TestClient(create_app(Settings(_env_file=None, data_dir=tmp_path/'auth', api_token='test-auth'))) as secured:
        assert secured.get('/api/chats').status_code == 401


def test_pending_and_stale_quote_rejected_without_persisting_turn(env):
    app, client, quote_id = env
    chat = conversation(client, [quote_id])

    def complete(req):
        current = client.get(f"/api/chats/{chat['chat_id']}").json()
        assert current['busy'] is True
        assert request(client, current).status_code == 409
        assert client.delete(f"/api/chats/{chat['chat_id']}").status_code == 409
        assert client.patch('/api/edit/' + quote_id, json={'title': '변경'}).status_code == 200
        return model_reply(quote_id)

    mock(app, complete)
    response = request(client, chat)
    assert response.status_code == 409, response.text
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").json()['total'] == 0
    assert client.get(f"/api/chats/{chat['chat_id']}").json()['busy'] is False


def test_context_limits_and_history_window(env):
    app, client, quote_id = env
    app.state.chat.config.chat_history_messages = 2
    mock(app, lambda req: model_reply(quote_id))
    chat = conversation(client, [quote_id])
    for index in range(3):
        response = request(client, chat)
        assert response.status_code == 201
        result = response.json()
        chat = result['chat']
    assert result['assistant_message']['metadata']['history_truncated'] is True
    assert result['assistant_message']['metadata']['history_messages_used'] == 2
    app.state.chat.config.chat_max_context_characters = 2000
    response = request(client, chat)
    assert response.status_code == 413
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").json()['total'] == 6


def test_trash_and_purge_remove_chat_copies(env):
    app, client, quote_id = env
    mock(app, lambda req: model_reply(quote_id))
    chat = request(client, conversation(client, [quote_id])).json()['chat']
    assert client.delete('/api/quotes/' + quote_id).status_code == 200
    assert client.get('/api/chats').json()['total'] == 0
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").status_code == 404
    assert request(client, chat).status_code == 404
    # This synthetic quote has no stored original. Purging it must still remove
    # all conversational copies and their message foreign keys.
    assert client.delete('/api/trash/' + quote_id).status_code == 200
    with app.state.db.sessions() as session:
        assert session.get(QuoteChat, chat['chat_id']) is None
        assert session.scalar(select(func.count()).select_from(ChatMessage)) == 0


def test_restoring_quotation_restores_conversation_access(env):
    app, client, _ = env
    pdf = make_pdf('Synthetic', ['견적번호: CHAT-RESTORE', '총액: 275000',
                                 '품명 수량 단위 단가 금액', '1 장비 1 EA 275000 275000'])
    quote_id = client.post('/api/add', files={'file': ('test.pdf', pdf)}).json()['quote_id']
    assert client.post('/api/extract', json={'quote_id': quote_id, 'provider': 'local'}).status_code == 202
    mock(app, lambda req: model_reply(quote_id))
    chat = request(client, conversation(client, [quote_id])).json()['chat']
    assert client.delete('/api/quotes/' + quote_id).status_code == 200
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").status_code == 404
    assert client.post(f'/api/quotes/{quote_id}/restore').status_code == 200
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").json()['total'] == 2


def test_chat_delete_and_restart_recovery(env):
    app, client, quote_id = env
    mock(app, lambda req: model_reply(quote_id))
    chat = request(client, conversation(client, [quote_id])).json()['chat']
    with app.state.db.sessions.begin() as session:
        session.get(QuoteChat, chat['chat_id']).pending_request_id = uid()
    with TestClient(create_app(app.state.config)) as restarted:
        recovered = restarted.get(f"/api/chats/{chat['chat_id']}").json()
        assert recovered['busy'] is False and recovered['version'] > chat['version']
        assert restarted.delete(f"/api/chats/{chat['chat_id']}").status_code == 200
        assert restarted.get(f"/api/chats/{chat['chat_id']}").status_code == 404
        assert restarted.get('/api/quotes/' + quote_id).status_code == 200
    with app.state.db.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ChatMessage)) == 0


def test_multiple_quotes_include_verified_decimal_comparison(env):
    app, client, first_id = env
    second_id = seed(app, items=[{'item_name': '가상 센서', 'specification': 'TEST', 'quantity': '10', 'unit_price': '24000', 'amount': '240000', 'unit': 'EA'}])

    def complete(req):
        body = json.loads(req.content)
        context = json.loads(body['messages'][1]['content'].split('\n', 1)[1])
        assert context['verified_comparison']['pairs'][0]['price_difference'] == '-1000'
        assert len(context['quotes']) == 2
        return model_reply(first_id, path='items.0.unit_price', answer='첫 견적의 단가는 25,000원입니다.')

    mock(app, complete)
    assert request(client, conversation(client, [first_id, second_id])).status_code == 201


def test_source_context_is_bounded_and_citations_cannot_escape_selection(env):
    app, client, quote_id = env
    with app.state.db.sessions.begin() as session:
        session.get(Quote, quote_id).extraction_raw = {'text': 'Z'*15000}

    def complete(req):
        body = json.loads(req.content)
        context = json.loads(body['messages'][1]['content'].split('\n', 1)[1])
        assert len(context['quotes'][0]['source_chunks']) == 12
        assert context['source_text_truncated'] == [quote_id]
        return model_reply(quote_id, path='source_chunks.11')

    mock(app, complete)
    chat = conversation(client, [quote_id])
    result = request(client, chat).json()
    assert result['assistant_message']['metadata']['source_text_truncated'] == [quote_id]
    assert result['assistant_message']['sources'][0]['value'] == 'Z'*1000
    mock(app, lambda req: model_reply(uid()))
    assert request(client, result['chat']).status_code == 502


@pytest.mark.parametrize('mode', ['timeout', 'invalid', 'truncated'])
def test_bad_responses_fail_without_partial_messages(env, mode):
    app, client, quote_id = env

    def complete(req):
        if mode == 'timeout':
            raise httpx.ReadTimeout('secret-network-detail')
        if mode == 'invalid':
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': 'not JSON'}}]})
        return httpx.Response(200, json={'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]})

    mock(app, complete)
    chat = conversation(client, [quote_id])
    response = request(client, chat)
    assert response.status_code == (504 if mode == 'timeout' else 502)
    assert 'secret-network-detail' not in response.text
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").json()['total'] == 0


def test_model_selection_switching_usage_and_restart(env):
    app, client, quote_id = env
    choices = client.get('/api/chats/models').json()
    assert choices['default_model'] == 'solar-pro4'
    assert {m['id'] for m in choices['items']} == {'solar-pro4', 'solar-mini4'}
    captured = []

    def complete(req):
        body = json.loads(req.content)
        captured.append(body)
        response = model_reply(quote_id)
        result = response.json()
        result['model'] = body['model'] + '-snapshot'
        return httpx.Response(200, json=result)

    mock(app, complete)
    created = client.post('/api/chats', json={'quote_ids': [quote_id], 'model': 'solar-mini4'})
    assert created.status_code == 201
    chat = created.json()
    assert chat['model'] == 'solar-mini4' and chat['usage']['total_tokens'] == 0
    first = request(client, chat).json()
    assert first['assistant_message']['metadata']['requested_model'] == 'solar-mini4'
    assert first['assistant_message']['metadata']['model'] == 'solar-mini4-snapshot'
    assert first['chat']['usage']['total_tokens'] == 120
    assert client.patch(f"/api/chats/{chat['chat_id']}", json={'model': 'solar-pro4', 'expected_version': chat['version']}).status_code == 409
    switched = client.patch(f"/api/chats/{chat['chat_id']}", json={'model': 'solar-pro4', 'expected_version': first['chat']['version']})
    assert switched.status_code == 200
    chat = switched.json()
    assert chat['model'] == 'solar-pro4' and chat['usage']['total_tokens'] == 120
    second = request(client, chat, '그럼 유효기간은?').json()
    assert captured[0]['model'] == 'solar-mini4' and captured[1]['model'] == 'solar-pro4'
    assert captured[1]['messages'][3]['content'] == first['assistant_message']['content']
    usage = client.get(f"/api/chats/{chat['chat_id']}/usage").json()
    assert usage['assistant_messages'] == usage['reported_messages'] == 2
    assert usage['prompt_tokens'] == 200 and usage['completion_tokens'] == 40 and usage['total_tokens'] == 240
    assert usage['complete'] is True and usage['basis'] == 'saved_answers'
    assert {row['model']: row['total_tokens'] for row in usage['by_model']} == {'solar-mini4': 120, 'solar-pro4': 120}
    assert second['chat']['usage'] == usage
    assert client.get('/api/chats/usage').json() == usage
    assert client.get('/api/chats').json()['items'][0]['model'] == 'solar-pro4'
    with TestClient(create_app(app.state.config)) as restarted:
        restored = restarted.get(f"/api/chats/{chat['chat_id']}").json()
        assert restored['model'] == 'solar-pro4' and restored['usage'] == usage
        messages = restarted.get(f"/api/chats/{chat['chat_id']}/messages").json()['items']
        assert messages[1]['metadata']['requested_model'] == 'solar-mini4'


def test_model_validation_and_busy_switching(env):
    app, client, quote_id = env
    assert client.post('/api/chats', json={'quote_ids': [quote_id], 'model': 'unapproved'}).status_code == 422
    chat = conversation(client, [quote_id])
    assert client.patch(f"/api/chats/{chat['chat_id']}", json={'model': 'unapproved', 'expected_version': chat['version']}).status_code == 422

    def complete(req):
        current = client.get(f"/api/chats/{chat['chat_id']}").json()
        result = client.patch(f"/api/chats/{chat['chat_id']}", json={'model': 'solar-mini4', 'expected_version': current['version']})
        assert result.status_code == 409
        return model_reply(quote_id)

    mock(app, complete)
    assert request(client, chat).status_code == 201


def test_missing_and_failed_usage_is_not_reported_as_complete(env):
    app, client, quote_id = env

    def missing_usage(req):
        response = model_reply(quote_id).json()
        response['usage'] = {'prompt_tokens': 100, 'completion_tokens': -1, 'total_tokens': True}
        return httpx.Response(200, json=response)

    mock(app, missing_usage)
    chat = request(client, conversation(client, [quote_id])).json()['chat']
    usage = chat['usage']
    assert usage['prompt_tokens'] == 100 and usage['total_tokens'] == 0
    assert usage['complete'] is False and usage['missing_usage_messages'] == 1
    mock(app, lambda req: model_reply(quote_id, path='nonexistent'))
    assert request(client, chat).status_code == 502
    assert client.get('/api/chats/usage').json() == usage
    assert client.get('/api/chats/missing/usage').status_code == 404


def test_model_allowlist_and_legacy_sqlite_migration(tmp_path):
    database = tmp_path/'quotes.db'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE quote_chats (id VARCHAR(36) PRIMARY KEY, title VARCHAR(200) NOT NULL, quote_ids JSON NOT NULL, version INTEGER NOT NULL, pending_request_id VARCHAR(36), created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL)')
        connection.execute("INSERT INTO quote_chats VALUES ('legacy','Original title','[]',1,NULL,'2026-10-17','2026-10-17')")
    config = Settings(_env_file=None, data_dir=tmp_path, chat_model='solar-pro4', chat_allowed_models='solar-pro4, custom-model,custom-model')
    assert config.available_chat_models == ['solar-pro4', 'custom-model']
    for _ in range(2):
        with TestClient(create_app(config)) as client:
            with client.app.state.db.sessions() as session:
                chat = session.get(QuoteChat, 'legacy')
                assert chat.model is None and chat.title == 'Original title'
            models = client.get('/api/chats/models').json()
            assert {m['id'] for m in models['items']} == {'solar-pro4', 'custom-model'}


def test_global_usage_combines_chats_and_survives_soft_trash(env):
    app, client, quote_id = env
    mock(app, lambda req: model_reply(quote_id))
    first = request(client, conversation(client, [quote_id])).json()['chat']
    request(client, conversation(client, [quote_id]))
    assert client.get('/api/chats/usage').json()['total_tokens'] == 240
    assert client.delete('/api/quotes/' + quote_id).status_code == 200
    assert client.get(f"/api/chats/{first['chat_id']}/usage").status_code == 404
    assert client.get('/api/chats/usage').json()['total_tokens'] == 240
    assert client.delete(f"/api/chats/{first['chat_id']}").status_code == 200
    assert client.get('/api/chats/usage').json()['total_tokens'] == 120
