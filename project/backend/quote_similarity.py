"""Read-only recommendations and item comparison over saved archive fields."""
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re


def norm(value):
    return re.sub(r'[^0-9a-z가-힣]+', '', str(value or '').casefold())


def tokens(value):
    return set(re.findall(r'[a-z가-힣]+[a-z0-9가-힣]*|\d+[a-z]+', str(value or '').casefold()))


def models(item):
    return {word for word in tokens((item.get('name') or '') + ' ' + (item.get('model') or '') + ' ' + (item.get('specification') or ''))
            if len(word) >= 3 and any(c.isdigit() for c in word) and any(c.isalpha() for c in word)}


def item_affinity(current, old):
    a, b = norm(current.get('name')), norm(old.get('name'))
    if not a or not b:
        return (0, '')
    same_name = a == b
    common_model = models(current) & models(old)
    shared_name = tokens(current.get('name')) & tokens(old.get('name'))
    related = same_name or bool(shared_name and (a in b or b in a or len(shared_name) >= 2))
    if not related:
        return (0, '')
    sa, sb = norm(current.get('specification')), norm(old.get('specification'))
    if common_model:
        name_model = models({'name': current.get('name')}) & models({'name': old.get('name')})
        return (120 if same_name else 90, '같은 모델 표기가 있습니다' if name_model else '같은 규격 코드가 있습니다')
    if same_name and sa and sb and sa == sb:
        return (105, '품명과 규격이 같습니다')
    if same_name and sa and sb and sa != sb:
        return (75, '품명은 같지만 규격이 다릅니다')
    return (55 if same_name else 35, '품목명이 유사합니다. 규격을 확인하세요')


def parsed_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def recommend(current, archive):
    today = parsed_date(current.get('issue_date'))
    current_hash = Path(current.get('source_url') or '').stem
    result = []
    for candidate in archive:
        if candidate.get('id') == current.get('id') or candidate.get('deleted_at'):
            continue
        if current_hash and Path(candidate.get('source_url') or '').stem == current_hash:
            continue
        candidate_date = parsed_date(candidate.get('issue_date'))
        if today and candidate_date and candidate_date >= today:
            continue
        matches = []
        for i, item in enumerate(current.get('items') or []):
            for j, other in enumerate(candidate.get('items') or []):
                score, reason = item_affinity(item, other)
                if score:
                    matches.append(dict(current_row=i + 1, past_row=j + 1, score=score, reason=reason,
                                        item=item.get('name') or other.get('name') or '품목명 미기재'))
        if not matches:
            continue
        matches.sort(key=lambda row: -row['score'])
        dated = bool(today and candidate_date)
        result.append(dict(id=candidate['id'], source_name=candidate.get('source_name'),
                           project_name=candidate.get('project_name'), issue_date=candidate.get('issue_date'),
                           chronology='past' if dated else 'unconfirmed',
                           reason=matches[0]['reason'], match=matches[0], score=matches[0]['score'],
                           matching_items=len({m['current_row'] for m in matches})))
    return sorted(result, key=lambda row: (row['chronology'] != 'past', -row['score'], row['issue_date'] or ''))


def number(value):
    if value is None or value == '':
        return None
    try:
        n = Decimal(str(value))
        return n if n.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def relation(item, items):
    if not item.get('is_component'):
        return ('주 품목', '')
    index = item.get('parent_index')
    parent = items[index] if isinstance(index, int) and 0 <= index < len(items) else None
    return ('구성품', norm(parent.get('name')) if parent else '')


def evidence(quote, item, index):
    result = dict(quote_id=quote['id'], document=quote.get('source_name') or quote.get('project_name') or '문서명 미기재',
                  source_url=quote.get('source_url'), row=index + 1, original_text=item.get('original_text') or '')
    source = item.get('source')
    if isinstance(source, dict):
        result['location'] = {key: source[key] for key in ('page', 'sheet', 'cell') if source.get(key) is not None}
    return result


def compare_pair(current, past, selected=None):
    selected = selected or {}
    current_items, old_items = current.get('items') or [], past.get('items') or []
    rows, used = [], set()
    for i, item in enumerate(current_items):
        choices = []
        for j, old in enumerate(old_items):
            score, reason = item_affinity(item, old)
            if score:
                choices.append((score, j, reason))
        choices.sort(reverse=True)
        j = selected.get(i, choices[0][1] if choices else None)
        if j is not None and (not isinstance(j, int) or j < 0 or j >= len(old_items) or not any(choice[1] == j for choice in choices)):
            raise ValueError('선택한 과거 품목은 대응 후보가 아닙니다.')
        old = old_items[j] if j is not None else None
        reasons = []
        status = 'comparable'
        if old is None:
            status = 'incompatible'; reasons.append('대응되는 과거 품목이 없습니다.')
        else:
            if i not in selected and len(choices) > 1 and choices[0][0] == choices[1][0]:
                status = 'review'; reasons.append('대응 가능한 과거 품목이 여러 개입니다. 행을 확인하세요.')
            if j in used:
                status = 'review'; reasons.append('같은 과거 품목에 현재 품목이 여러 개 대응됩니다.')
            used.add(j)
            if norm(item.get('name')) != norm(old.get('name')):
                status = 'review'; reasons.append('품목명이 완전히 같지 않습니다.')
            for key, label in [('specification', '규격'), ('unit', '단위')]:
                a, b = norm(item.get(key)), norm(old.get(key))
                if not a or not b:
                    status = 'review'; reasons.append(f'{label}이 한쪽 이상 미기재입니다.')
                elif a != b:
                    status = 'incompatible' if key == 'unit' else 'review'
                    reasons.append(f'{label}이 다릅니다: 과거 {old.get(key)} / 현재 {item.get(key)}.')
            for key, label in [('currency', '통화'), ('tax_note', 'VAT 조건')]:
                a, b = norm(current.get(key)), norm(past.get(key))
                if not a or not b or '미기재' in a or '미기재' in b:
                    status = 'review'; reasons.append(f'{label}이 한쪽 이상 미기재입니다.')
                elif a != b:
                    status = 'incompatible' if key == 'currency' else 'review'
                    reasons.append(f'{label}이 다릅니다: 과거 {past.get(key)} / 현재 {current.get(key)}.')
            a, b = number(item.get('quantity')), number(old.get('quantity'))
            if a is None or b is None:
                status = 'review'; reasons.append('수량이 한쪽 이상 미기재입니다.')
            elif a != b:
                status = 'review'; reasons.append(f'수량이 다릅니다: 과거 {b} / 현재 {a}.')
            a, b = item.get('option_group') or '', old.get('option_group') or ''
            if a or b:
                status = 'review'; reasons.append('선택 옵션이 포함됩니다. 같은 선택 조건인지 확인하세요.' if norm(a) == norm(b) else '선택 옵션 조건이 다르거나 한쪽에 미기재입니다.')
            if any((item.get('option_choice'),old.get('option_choice'),item.get('option_condition'),old.get('option_condition'))):
                if (item.get('option_choice') or '') != (old.get('option_choice') or '') or (item.get('option_condition') or '') != (old.get('option_condition') or ''):
                    status = 'review'; reasons.append('옵션 선택지 또는 선택 조건이 다릅니다.')
            ra, rb = relation(item, current_items), relation(old, old_items)
            if ra != rb or (ra[0] == '구성품' and not ra[1]):
                status = 'review'; reasons.append('패키지·구성품 관계나 상위 품목을 확인하세요.')
            if number(item.get('unit_price')) is None or number(old.get('unit_price')) is None:
                status = 'review'; reasons.append('단가가 한쪽 이상 미기재입니다.')
            if norm(item.get('unit')) and norm(old.get('unit')) and norm(item.get('unit')) != norm(old.get('unit')):
                status = 'incompatible'
            if norm(current.get('currency')) and norm(past.get('currency')) and norm(current.get('currency')) != norm(past.get('currency')):
                status = 'incompatible'
        if not reasons:
            reasons.append('품명·규격·단위·수량·통화·VAT 조건과 품목 관계가 같습니다.')
        delta = percent = None
        if status == 'comparable':
            now, before = number(item['unit_price']), number(old['unit_price'])
            delta = float(now - before)
            if before != 0:
                percent = float((now - before) / before * 100)
            else:
                reasons.append('과거 단가가 0이어서 변화율은 표시하지 않습니다.')
        rows.append(dict(status=status, reasons=reasons, current=dict(item, row=i + 1),
                         past=dict(old, row=j + 1) if old is not None else None,
                         candidates=[c[1] + 1 for c in choices if c[0] == choices[0][0]] if choices else [],
                         delta=delta, percent=percent,
                         current_evidence=evidence(current, item, i),
                         past_evidence=evidence(past, old, j) if old is not None else None))
    for j, old in enumerate(old_items):
        if j not in used:
            rows.append(dict(status='incompatible', reasons=['현재 문서에 대응되는 품목이 없습니다.'],
                             current=None, past=dict(old, row=j + 1), candidates=[], delta=None, percent=None,
                             current_evidence=None, past_evidence=evidence(past, old, j)))
    order = {'review': 0, 'incompatible': 1, 'comparable': 2}
    rows.sort(key=lambda row: order[row['status']])
    conditions = []
    for key, label in [('delivery', '납기'), ('payment_terms', '결제 조건')]:
        a, b = current.get(key) or '', past.get(key) or ''
        if a != b or not a:
            conditions.append(dict(label=label, past=b or '미기재', current=a or '미기재'))
    return dict(direction='비교 문서 → 현재', current=dict(id=current['id'], name=current.get('source_name') or current.get('project_name') or '문서명 미기재', issue_date=current.get('issue_date'), source_url=current.get('source_url'), currency=current.get('currency')),
                past=dict(id=past['id'], name=past.get('source_name') or past.get('project_name') or '문서명 미기재', issue_date=past.get('issue_date'), source_url=past.get('source_url'), currency=past.get('currency')),
                chronology='past' if parsed_date(current.get('issue_date')) and parsed_date(past.get('issue_date')) and parsed_date(past['issue_date']) < parsed_date(current['issue_date']) else 'unconfirmed',
                rows=rows, conditions=conditions,
                summary={key: sum(row['status'] == key for row in rows) for key in order},
                scope='저장된 추출·정정 값의 비교입니다. 원본 전체를 자동 대조한 결과는 아닙니다.')
