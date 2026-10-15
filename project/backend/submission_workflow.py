"""A read-only, staged Studio workflow for existing archived quotations."""
import copy
import json
import re
import tempfile
import time
import uuid
from pathlib import Path

from sqlalchemy import Column, String, Table, Text, select

import domain as d
from agent_workflow import build_input
from quote_similarity import compare_pair
from user_agent import AgentError, AgentSettings, merge_agent_result, run_agent

flows = Table('analysis_flows', d.meta, Column('id', String(36), primary_key=True), Column('payload', Text, nullable=False))
d.meta.create_all(d.engine)
STAGES = ('extract', 'classify', 'review', 'compare')
TYPES = {'일반 품목 견적', '대체 옵션 견적', '패키지·구성품 견적', '옵션·패키지 혼합 견적', '판단 보류'}


def save(record):
    with d.engine.begin() as conn:
        conn.execute(flows.delete().where(flows.c.id == record['id']))
        conn.execute(flows.insert().values(id=record['id'], payload=json.dumps(record, ensure_ascii=False)))
    return record


def get(ident):
    with d.engine.connect() as conn:
        row = conn.execute(select(flows.c.payload).where(flows.c.id == ident)).first()
    if not row:
        return None
    record = json.loads(row[0])
    visible = {q['id'] for q in d.all_quotes()}
    return record if all(ident in visible for ident in record['quote_ids']) else None


def recent():
    with d.engine.connect() as conn:
        records = [json.loads(row[0]) for row in conn.execute(select(flows.c.payload))]
    visible = {q['id'] for q in d.all_quotes()}
    return sorted((r for r in records if all(i in visible for i in r['quote_ids'])),
                  key=lambda r: r['started_at'], reverse=True)[:20]


def start(quotes, agents):
    if not 1 <= len(quotes) <= 5 or len({q['id'] for q in quotes}) != len(quotes):
        raise AgentError('중복 없이 현재 문서와 비교 문서 최대 4개를 선택해주세요.')
    if set(agents) != {'extract', 'review', 'compare'}:
        raise AgentError('추출·검토·비교 에이전트 연결을 확인해주세요.')
    for config in agents.values():
        if not isinstance(config, dict) or not re.fullmatch(r'agt_[A-Za-z0-9_-]{4,160}', str(config.get('agent_id', ''))) or not re.fullmatch(r'[1-9][0-9]{0,8}', str(config.get('config_id', ''))):
            raise AgentError('연결 설정의 Agent ID·설정 버전을 확인해주세요.')
    clean_agents={role:{'agent_id':config['agent_id'],'config_id':str(config['config_id'])} for role,config in agents.items()}
    record = dict(id=str(uuid.uuid4()), quote_ids=[q['id'] for q in quotes],
                  quote_versions={q['id']: q['version'] for q in quotes},
                  document_names={q['id']: q.get('source_name') or q.get('project_name') or '문서명 미기재' for q in quotes},
                  agents=clean_agents, status='running', started_at=d.now(),
                  stages={key: dict(status='pending') for key in STAGES},
                  scope='Studio 해석과 저장 데이터의 코드 진단입니다. 원본과 추출 결과를 함께 보낸 검토도 모든 원문 정확성을 보장하지 않습니다.')
    if len(quotes) == 1:
        record['stages']['compare'] = dict(status='skipped', reason='비교 문서를 선택하지 않았습니다.')
    return save(record)


def stage(record, key, **values):
    record['stages'][key].update(values)
    save(record)


def original_path(q):
    filename = Path(q.get('source_url') or '').name
    if not re.fullmatch(r'[a-f0-9]{64}\.(pdf|xls|xlsx|docx|png|jpe?g)', filename):
        raise AgentError('보관된 원본 파일 경로를 확인해주세요.')
    path = d.STORAGE / 'files' / filename
    if not path.is_file():
        raise AgentError('보관된 원본 파일을 찾지 못했습니다.')
    return path


def normalized_extraction(source, output):
    if not isinstance(output, dict):
        raise AgentError('추출 결과의 JSON 형식을 확인해주세요.')
    result = copy.deepcopy(output)
    if 'items_json' in result and 'items' not in result:
        raw = result['items_json']
        if isinstance(raw, list) and len(raw) == 1:
            raw = raw[0]
        try:
            result['items'] = json.loads(raw)
        except (TypeError, ValueError):
            raise AgentError('추출 결과의 품목 배열을 확인해주세요.') from None
    items = result.get('items')
    if not isinstance(items, list) or not items or len(items) > 300 or any(not isinstance(row, dict) or not isinstance(row.get('name'), str) for row in items):
        raise AgentError('추출 결과의 품목 이름·목록을 확인해주세요.')
    allowed_item = {'name', 'model', 'specification', 'unit', 'quantity', 'unit_price', 'amount', 'is_component', 'parent_index', 'option_group', 'option_choice', 'option_condition', 'original_text'}
    if any(set(row) - allowed_item for row in items):
        raise AgentError('추출 결과의 품목 필드가 프로젝트 형식과 다릅니다.')
    for row in items:
        for key in ('quantity','unit_price','amount'):
            raw=row.get(key)
            if isinstance(raw,str) and raw.strip():
                # Studio may include the explicitly extracted currency in a numeric item field.
                match=re.fullmatch(r'\s*([+-]?\d[\d,]*(?:\.\d+)?)\s*([A-Z]{3})\s*',raw)
                if match:
                    if match.group(2)!=result.get('currency'):
                        raise AgentError('품목 금액의 통화가 문서 통화와 다릅니다. 원본에서 확인해주세요.')
                    row[key]=match.group(1)
    for index, row in enumerate(items):
        parent = row.get('parent_index')
        if row.get('is_component') and (not isinstance(parent, int) or not 0 <= parent < len(items) or parent == index):
            raise AgentError(f'{index+1}행 구성품의 상위 패키지 번호를 확인해주세요.')
    analysis = dict(id=source['id'], version=source['version'], source_name=source.get('source_name'),
                    source_url=source.get('source_url'), issue_date='', currency='', tax_note='',
                    items=[], customer='', delivery='', payment_terms='', source_total=None,
                    subtotal=None, total=None, tax=None, tax_rate=None)
    merge_agent_result(analysis, result)
    try:
        d.calculate(analysis)
    except ValueError:
        raise AgentError('추출 결과의 숫자나 품목 관계를 확인해주세요.') from None
    return analysis


def checked_evidence(output, item_count):
    raw = output.get('item_evidence_json')
    if raw is None:
        return []
    try:
        rows = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        raise AgentError('품목 근거 배열의 JSON 형식을 확인해주세요.') from None
    if not isinstance(rows, list) or len(rows) > 300:
        raise AgentError('품목 근거 배열의 길이를 확인해주세요.')
    clean = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('item_index'), int) or not 0 <= row['item_index'] < item_count:
            raise AgentError('품목 근거의 행 번호를 확인해주세요.')
        location = {key: str(row[key])[:120] for key in ('page', 'sheet', 'cell', 'line') if row.get(key) is not None}
        clean.append({'item_index': row['item_index'], 'location': location, 'excerpt': str(row.get('excerpt') or '')[:500], 'origin': 'Studio 제안 · 원본 확인 필요'})
    return clean


def checked_report(output, kind):
    if not isinstance(output, dict) or not isinstance(output.get('summary'), str):
        raise AgentError('에이전트 결과의 요약 형식을 확인해주세요.')
    key = 'issues' if kind == 'review' else 'item_matches'
    legacy = 'findings' if kind == 'review' else 'differences'
    rows = output.get(key)
    if rows is None and isinstance(output.get(legacy), list):
        rows = [{'what': value, 'why': 'Studio의 이전 문자열 결과입니다. 원본 근거를 확인하세요.', 'source': '', 'action': '원본에서 확인'} for value in output[legacy] if isinstance(value, str)]
    if not isinstance(rows, list) or len(rows) > 100 or any(not isinstance(row, dict) for row in rows):
        raise AgentError('에이전트 결과의 확인 항목 형식을 확인해주세요.')
    if key in output:
        for row in rows:
            fields=('what','why','observed','source','action') if kind=='review' else ('other_document_id','status','reason','current_value','other_value','source','action')
            if any(field in row and not isinstance(row[field], str) for field in fields):
                raise AgentError('에이전트 결과의 설명 필드 형식을 확인해주세요.')
            if kind=='review' and not isinstance(row.get('what'), str):
                raise AgentError('검토 항목의 제목을 확인해주세요.')
            if kind=='compare' and (not isinstance(row.get('reason'), str) or row.get('status') not in ('비교 가능','조건 확인 필요','비교 불가')):
                raise AgentError('비교 품목의 상태와 이유를 확인해주세요.')
    conditions=output.get('conditions',[])
    if kind=='compare' and (not isinstance(conditions,list) or len(conditions)>100 or any(not isinstance(row,dict) or not isinstance(row.get('label'),str) or not isinstance(row.get('values'),str) for row in conditions)):
        raise AgentError('거래 조건 차이의 형식을 확인해주세요.')
    return dict(summary=output['summary'][:4000], items=rows, conditions=conditions if kind=='compare' else [], classification=output.get('review_level' if kind == 'review' else 'comparison_level') or output.get('risk_level') or '',
                scope=output.get('scope') or ('원본 및 추출 결과 입력' if kind == 'review' else '저장된 비교 문서 입력'),
                legacy=key not in output)


def run(record_id, quotes, api_key, runner=run_agent):
    record = get(record_id)
    if record is None:
        return
    current, others = quotes[0], quotes[1:]
    try:
        source = original_path(current)
        config = record['agents']['extract']
        stage(record, 'extract', status='running', started_at=d.now())
        began = time.monotonic()
        output, metadata = runner(source, AgentSettings(api_key, config['agent_id'], config['config_id']))
        analysis = normalized_extraction(current, output)
        evidence = checked_evidence(output, len(analysis['items']))
        stage(record, 'extract', status='completed', completed_at=d.now(), elapsed_seconds=round(time.monotonic()-began, 2),
              metadata=metadata, result={'fields': {key: analysis.get(key) for key in ('number','customer','issuer','issue_date','currency','tax_note','delivery','payment_terms','subtotal','tax','total','source_total','notes')}, 'items': analysis['items'], 'evidence': evidence},
              input='보관 원본 파일', calculation_warnings=analysis.get('warnings', []))
    except Exception as error:
        stage(record, 'extract', status='failed', completed_at=d.now(), elapsed_seconds=round(time.monotonic()-began, 2) if 'began' in locals() else 0, error=str(error) if isinstance(error, AgentError) else '원본 추출을 완료하지 못했습니다.')
        for key in ('classify','review','compare'):
            if record['stages'][key]['status'] == 'pending':stage(record, key, status='skipped', reason='원본 추출이 완료되지 않았습니다.')
        record.update(status='failed', completed_at=d.now());save(record);return
    doc_type = output.get('document_type') if isinstance(output, dict) else None
    if doc_type in TYPES:
        stage(record, 'classify', status='completed', completed_at=d.now(), elapsed_seconds=0,
              metadata=metadata, result={'document_type':doc_type,'reason':str(output.get('classification_reason') or '')[:1000]},
              input='추출 에이전트의 Parse → Classify → Extract 분기')
    else:
        stage(record, 'classify', status='unverified', completed_at=d.now(), reason='Studio 결과에 문서 유형이 없어 분류를 확인하지 못했습니다. 이전 설정 버전을 확인해주세요.')
    with tempfile.TemporaryDirectory(prefix='quote-flow-', dir=d.STORAGE) as temporary:
        analysis_file = Path(temporary)/'extracted-fields.pdf'
        try:
            build_input(analysis_file, [analysis], '원본 추출 결과 / 원본 파일과 대조')
            config = record['agents']['review']
            stage(record, 'review', status='running', started_at=d.now())
            began = time.monotonic()
            review_output, review_meta = runner([source, analysis_file], AgentSettings(api_key, config['agent_id'], config['config_id']))
            review = checked_report(review_output, 'review')
            stage(record, 'review', status='completed', completed_at=d.now(), elapsed_seconds=round(time.monotonic()-began, 2),
                  metadata=review_meta, result=review, input='원본 파일 + 추출 결과 PDF')
        except Exception as error:
            stage(record, 'review', status='failed', completed_at=d.now(), error=str(error) if isinstance(error, AgentError) else '검토를 완료하지 못했습니다.',
                  elapsed_seconds=round(time.monotonic()-began, 2) if record['stages']['review']['status']=='running' else 0,
                  input='원본 파일 + 추출 결과 PDF')
        if others:
            try:
                code_comparison = [compare_pair(analysis, other) for other in others]
                stage(record, 'compare', code_comparison=code_comparison, code_scope='저장된 비교 문서와 이번 Studio 추출값을 코드로 비교')
                comparison_file = Path(temporary)/'comparison-fields.pdf'
                build_input(comparison_file, [analysis, *others], '추출 결과와 선택한 기존 견적 비교')
                config = record['agents']['compare']
                stage(record, 'compare', status='running', started_at=d.now())
                began = time.monotonic()
                compare_output, compare_meta = runner(comparison_file, AgentSettings(api_key, config['agent_id'], config['config_id']))
                comparison = checked_report(compare_output, 'compare')
                stage(record, 'compare', status='completed', completed_at=d.now(), elapsed_seconds=round(time.monotonic()-began, 2),
                      metadata=compare_meta, result=comparison, input='추출 결과 + 선택한 저장 문서 PDF')
            except Exception as error:
                stage(record, 'compare', status='failed', completed_at=d.now(), elapsed_seconds=round(time.monotonic()-began, 2) if record['stages']['compare']['status']=='running' else 0,
                      error=str(error) if isinstance(error, AgentError) else '비교를 완료하지 못했습니다. 저장값의 코드 비교는 볼 수 있습니다.')
    record.update(status='completed' if all(record['stages'][key]['status'] in ('completed','skipped') for key in STAGES) else 'partial', completed_at=d.now())
    save(record)
