"""Prepare Studio import drafts from the three existing exported workflows.

These files are local proposals until Studio import, save, export and a live run succeed.
"""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'submission_drafts'
OUT.mkdir(exist_ok=True)


def source(role):
    return json.loads((HERE / f'견적아카이브_{role}.json').read_text(encoding='utf-8'))


def write(role, doc):
    (OUT / f'견적아카이브_{role}.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prop(kind, description):
    return {'type': kind, 'description': description}


def branch(name, properties):
    return {'type': 'json_schema', 'json_schema': {'name': name, 'schema': {'type': 'object', 'properties': properties}}}


def classify(categories):
    return {'modelName': '', 'schema': {'type': 'json_schema', 'json_schema': {
        'name': 'document-classify', 'schema': {'type': 'string', 'oneOf': [
            {'const': label, 'description': description} for label, description in categories]}}}}


def extract_schema(label, instruction):
    base = copy.deepcopy(source('추출')['workflowConfig']['informationExtractConfiguration']['schemas'][0]['json_schema']['schema']['properties'])
    for key in ('subtotal', 'tax', 'total', 'tax_rate', 'source_total'):
        base[key] = prop('string', f'원문에 직접 표시된 {key}의 숫자만 출력. 미기재·선택 전 미확정이면 빈 문자열. 절대로 0으로 대신하지 않는다')
    base['document_type'] = prop('string', f'분류된 문서 유형을 그대로 출력: {label}')
    base['classification_reason'] = prop('string', '이 유형으로 분류했거나 판단을 보류한 원문 근거. 확인 불가하면 그 이유')
    base['items_json']['description'] = (
        instruction + ' 모든 품목을 순서대로 JSON 배열 문자열로 출력. 각 객체는 '
        'name,model,specification,unit,quantity,unit_price,amount,is_component,parent_index,option_group,option_choice,option_condition,original_text. '
        '모델은 명시된 경우만 쓰고 미기재 값은 null/빈 문자열. parent_index는 0부터 시작하는 상위 품목 행 번호. '
        'quantity,unit_price,amount에는 숫자만, 통화는 currency에 쓴다. '
        '같은 대체 선택 묶음은 같은 option_group을 쓰고 option_choice에 A/B 등 각 선택지, option_condition에 선택 조건 원문을 기록한다. '
        '원문 금액을 계산하거나 옵션·구성품을 합산하지 않는다.')
    base['item_evidence_json'] = prop('string', 'JSON 배열 문자열. 각 원소는 item_index(0부터), page/sheet/cell/line 중 실제 확인한 위치, excerpt(짧은 원문). 위치를 확인하지 못하면 빈 배열')
    base['notes']['description'] = '명시된 보증·설치·운송·특약·선택 조건을 원문 그대로 보존. 없으면 빈 문자열'
    return base


extract = source('추출')
config = extract['workflowConfig']
types = [
    ('일반 품목 견적', '옵션 그룹과 구성품 관계가 없는 일반 품목 견적', '독립 품목을 추출한다. 일반 품목으로 확정할 근거가 없으면 판단 보류로 분류한다.'),
    ('대체 옵션 견적', '서로 대체되는 선택 품목이나 선택 조건이 있다', '대체 품목을 모두 보존하고 같은 옵션의 option_group을 기록한다. 선택 여부와 합계를 임의 결정하지 않는다.'),
    ('패키지·구성품 견적', '상위 패키지와 하위 구성품의 포함 관계가 있다', '상위 품목과 모든 구성품을 각각 보존하고 구성품의 is_component=true, parent_index를 연결한다. 패키지와 구성품 금액을 중복 합산하지 않는다.'),
    ('옵션·패키지 혼합 견적', '대체 옵션과 패키지·구성품 관계가 모두 있다', '옵션 그룹과 패키지/구성품 계층을 동시에 보존한다. 옵션을 선택하거나 상위/하위 금액을 합산하지 않는다.'),
    ('판단 보류', '원문이 부족하거나 옵션·패키지 관계를 확정할 수 없다', '불명확한 관계를 임의로 일반 품목으로 처리하지 않는다. 확인한 품목과 원문을 보존하고 이유를 classification_reason에 쓴다.')]
config['pipelineType'] = 'classify-extract'
config['documentClassifyConfiguration'] = classify([(label, description) for label, description, _ in types])
config['informationExtractConfiguration'] = {'modelName': '', 'schemas': [
    {**branch(f'Extract_{i+1}', extract_schema(label, instruction)), 'mode': 'standard', 'modelName': ''}
    for i, (label, _, instruction) in enumerate(types)],
    'categorySchemaMapping': {label: f'Extract_{i+1}' for i, (label, _, _) in enumerate(types)}}
config['pipelineEdges'] = [{'id':'e0','source':{'nodeType':'parse'},'target':{'nodeType':'classify','name':'Classify-1'}}] + [
    {'id':f'e{i+1}','source':{'nodeType':'classify','name':'Classify-1'},
     'target':{'nodeType':'extract','name':f'Extract_{i+1}'}, 'condition':{'conditionName':label}}
    for i, (label, _, _) in enumerate(types)]
write('추출', extract)


review = source('검토')
review_rules = [
    '필수값·원본 금액 불일치·옵션 미선택·패키지 관계·VAT/통화/단위·모순 조건을 중요도순으로 구체적으로 확인한다.',
    '옵션·VAT·납기·결제·보증 해석이 필요한 부분을 중요도순으로 기록한다. 산술 결과는 코드 진단을 근거로만 사용한다.',
    '문제 없음도 원본과 추출 결과에서 실제 확인한 범위만 말한다. 검토하지 못한 필드는 검증했다고 쓰지 않는다.']
review_properties = {
    'summary': prop('string','이번 검토의 핵심 요약. 적정 가격이나 검토 완료를 선언하지 않는다'),
    'review_level': prop('string','확인 필요 / 주의 / 문제 없음'),
    'scope': prop('string','원본 파일과 별도 추출 결과 파일을 함께 읽은 범위. 전체 대조 여부를 추정하지 않는다'),
    'issues': {'type':'array','items':{'type':'object','properties':{
        'severity':prop('string','높음 / 보통 / 참고'),
        'what':prop('string','무엇을 확인할지'), 'why':prop('string','왜 확인이 필요한지'),
        'observed':prop('string','원본 또는 추출 결과에 명시된 값. 출처를 구분'),
        'source':prop('string','실제로 확인한 파일·페이지/시트/셀·품목 행. 없으면 미확인'),
        'action':prop('string','사용자가 원본에서 다음에 확인할 행동'),
        'item_row':prop('number','추출 결과의 1부터 시작하는 품목 행. 해당 없으면 0')}},
        'description':'중요도순 확인 사항. 원본 근거가 없으면 근거 없음으로 표시'} }
for index, schema in enumerate(review['workflowConfig']['informationExtractConfiguration']['schemas']):
    schema['json_schema']['schema']['properties'] = copy.deepcopy(review_properties)
    schema['json_schema']['schema']['properties']['issues']['description'] = review_rules[index]
write('검토', review)


compare = source('비교')
compare_rules = [
    '품명·모델·규격·단위·수량·통화·VAT·옵션·패키지 관계가 맞는 행만 비교 가능으로 제안한다.',
    '동일 품명 다른 규격, 옵션, 수량, VAT, 조건 차이를 각 품목에 연결해 조건 확인 필요로 제안한다.',
    '품목 대응이나 통화·단위·원본 단가가 불명확한 부분을 비교 불가로 설명한다.']
compare_properties = {
    'summary':prop('string','선택한 기존 문서들의 핵심 차이. 가격 우열·예상 절감액을 만들지 않는다'),
    'comparison_level':prop('string','비교 가능 / 조건부 비교 / 비교 불가'),
    'scope':prop('string','입력된 추출·저장값 비교 범위. 원본 전체 대조라 말하지 않는다'),
    'item_matches':{'type':'array','items':{'type':'object','properties':{
        'current_row':prop('number','첫 문서의 1부터 시작하는 품목 행'),
        'other_document_id':prop('string','대응 문서의 입력 id'),
        'other_row':prop('number','대응 문서의 1부터 시작하는 품목 행'),
        'status':prop('string','비교 가능 / 조건 확인 필요 / 비교 불가'),
        'reason':prop('string','대응 이유와 규격·수량·단위·통화·VAT·옵션·패키지 차이'),
        'current_value':prop('string','첫 문서에 명시된 값'),
        'other_value':prop('string','대응 문서에 명시된 값'),
        'source':prop('string','입력 문서와 행·원문 근거. 없으면 미확인'),
        'action':prop('string','사용자가 확인할 행동')}},
        'description':'품목 대응은 AI 제안이며 불명확하면 상태와 이유를 표시'},
    'conditions':{'type':'array','items':{'type':'object','properties':{
        'label':prop('string','납기 / 결제 / 보증 등 조건명'),
        'values':prop('string','문서별 원문 값'),
        'source':prop('string','입력 문서의 확인 가능한 위치')}},
        'description':'금액과 별도로 거래 조건 차이'} }
for index, schema in enumerate(compare['workflowConfig']['informationExtractConfiguration']['schemas']):
    schema['json_schema']['schema']['properties'] = copy.deepcopy(compare_properties)
    schema['json_schema']['schema']['properties']['item_matches']['description'] = compare_rules[index]
write('비교', compare)

print('Prepared local Studio drafts:', *(str(path) for path in OUT.glob('*.json')), sep='\n')
