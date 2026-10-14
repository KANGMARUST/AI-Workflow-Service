"""Studio analysis reports, separate from original quotation records."""
import json,re,uuid,tempfile
from pathlib import Path
from xml.sax.saxutils import escape
from sqlalchemy import Table,Column,String,Text,select
import domain as d
from user_agent import AgentError,run_agent

runs=Table('agent_runs',d.meta,Column('id',String(36),primary_key=True),Column('payload',Text,nullable=False))
d.meta.create_all(d.engine)

def save_run(record):
    with d.engine.begin() as conn:
        conn.execute(runs.delete().where(runs.c.id==record['id']))
        conn.execute(runs.insert().values(id=record['id'],payload=json.dumps(record,ensure_ascii=False)))
    return record

def list_runs():
    visible={q['id'] for q in d.all_quotes()}
    with d.engine.connect() as conn:records=[json.loads(row[0]) for row in conn.execute(select(runs.c.payload))]
    return sorted([r for r in records if all(i in visible for i in r['quote_ids'])],key=lambda r:r['started_at'],reverse=True)

def build_input(path,quotes,kind):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
    from reportlab.lib.pagesizes import A4
    font='QuoteNanum'
    if font not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(font,str(Path(__file__).parent/'fonts'/'NanumGothic-Regular.ttf')))
    style=ParagraphStyle('analysis',fontName=font,fontSize=9,leading=13,wordWrap='CJK')
    story=[Paragraph('기존 견적 분석 입력 / '+escape(kind),style),Spacer(1,12)]
    fields=('id','version','source_name','number','customer','issuer','issue_date','project_name','currency','tax_note','subtotal','tax','total','source_total','source_total_kind','delivery','ship_to','payment_terms','notes','items','detailed_fields','item_specifications')
    for q in quotes:
        text=json.dumps({k:q.get(k) for k in fields},ensure_ascii=False,indent=2)
        if len(text)>300000:raise AgentError('분석 자료가 너무 큽니다. 작은 문서부터 선택해주세요.')
        for line in text.splitlines():
            for start in range(0,max(1,len(line)),160):story.append(Paragraph(escape(line[start:start+160]) or ' ',style))
        story.append(Spacer(1,16))
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=35,leftMargin=35,topMargin=35,bottomMargin=35).build(story)

def execute(kind,quotes,settings,runner=run_agent):
    if kind not in ('extract','review','compare'):raise AgentError('지원하지 않는 분석 종류입니다.')
    if len(quotes) not in (range(2,6) if kind=='compare' else [1]):raise AgentError('비교는 문서 2~5개, 추출·검토는 문서 1개를 선택해주세요.')
    record=dict(id=str(uuid.uuid4()),kind=kind,quote_ids=[q['id'] for q in quotes],quote_versions={q['id']:q['version'] for q in quotes},status='running',started_at=d.now(),agent_id=settings.agent_id,config_id=settings.config_id)
    save_run(record)
    try:
        with tempfile.TemporaryDirectory(prefix='quote-agent-',dir=d.STORAGE) as directory:
            path=Path(directory)/'analysis.pdf'
            if kind=='extract':
                filename=Path(quotes[0].get('source_url') or '').name
                if not re.fullmatch(r'[a-f0-9]{64}\.(pdf|xls|xlsx|docx|png|jpe?g)',filename):raise AgentError('지원하는 원본 파일이 연결되지 않았습니다.')
                original=d.STORAGE/'files'/filename
                if not original.is_file():raise AgentError('원본 파일을 찾지 못했습니다.')
                path=original
            else:build_input(path,quotes,kind)
            result,metadata=runner(path,settings)
        required={'extract':('customer','items','items_json'),'review':('summary','findings'),'compare':('summary','differences')}[kind]
        if not any(k in result for k in required) or (kind!='extract' and not all(k in result for k in required)):raise AgentError('해당 역할의 에이전트 출력 스키마를 확인해주세요.')
        record.update(status='completed',completed_at=d.now(),result=result,metadata=metadata)
    except AgentError as error:
        record.update(status='failed',completed_at=d.now(),error=str(error))
        save_run(record)
        raise
    except Exception:
        record.update(status='failed',completed_at=d.now(),error='분석 입력 준비 또는 결과 저장에 실패했습니다.')
        save_run(record)
        raise AgentError(record['error']) from None
    return save_run(record)
