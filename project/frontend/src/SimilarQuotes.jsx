import React, {useState} from 'react';
import {ArrowRight, CheckCircle2, CircleAlert, FileText, Search, XCircle} from 'lucide-react';
import {api, fileURL} from './api';

const labels={comparable:'비교 가능',review:'조건 확인 필요',incompatible:'비교 불가'};
const icons={comparable:CheckCircle2,review:CircleAlert,incompatible:XCircle};
const shown=value=>value===null||value===undefined||value===''?'미기재':String(value);
const number=value=>value===null||value===undefined?'미기재':new Intl.NumberFormat('ko-KR',{maximumFractionDigits:20}).format(value);
const percent=value=>new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2}).format(value);
const amount=(value,currency)=>value===null||value===undefined?'미기재':`${number(value)} ${currency||'통화 미기재'}`;
const date=value=>value?String(value).slice(0,10).replaceAll('-','.'):'미기재';

function Source({source}){
  if(!source)return null;
  const location=source.location||{};
  return <div className="similar-source"><span>{source.document} · {source.row}행{location.page!=null?` · ${location.page}쪽`:''}{location.sheet?` · ${location.sheet} 시트`:''}{location.cell?` · ${location.cell} 셀`:''}</span>{source.source_url&&<a href={fileURL(source.source_url)} target="_blank" rel="noreferrer"><FileText size={15}/>원본 열기</a>}{source.original_text&&<details><summary>저장된 품목 원문</summary><p>{source.original_text}</p></details>}</div>;
}

export default function SimilarQuotes({quote}){
  const [phase,setPhase]=useState('idle');
  const [candidates,setCandidates]=useState([]);
  const [report,setReport]=useState(null);
  const [error,setError]=useState('');
  const [selected,setSelected]=useState({});
  async function find(){setPhase('loading');setError('');setReport(null);try{setCandidates(await api(`/quotes/${quote.id}/similar`));setPhase('ready');}catch(e){setError(`${e.message} 다시 찾기를 눌러주세요.`);setPhase('error');}}
  async function choose(id,mapping={}){setPhase('comparing');setError('');try{const matches=Object.entries(mapping).map(([a,b])=>`${a}:${b}`).join(',');setReport(await api(`/quotes/${quote.id}/compare/${id}${matches?`?matches=${encodeURIComponent(matches)}`:''}`));setSelected(mapping);setPhase('ready');}catch(e){setError(`${e.message} 다른 문서를 선택하거나 다시 시도해주세요.`);setPhase('error');}}
  const referenceLabel=report?.chronology==='past'?'과거':'비교 문서';
  return <section className="panel similar-panel" aria-label="비슷한 과거 견적 비교"><div className="panel-title"><div><h2>비슷한 과거 견적 찾기</h2><p>품목과 규격으로 후보를 찾고, 단가를 비교할 조건인지 먼저 확인해요.</p></div><button className="button primary" onClick={find} disabled={phase==='loading'||phase==='comparing'} title={phase==='loading'||phase==='comparing'?'검색이 끝나면 다시 실행할 수 있습니다.':''}><Search size={16}/>후보 찾기</button></div>
    {phase==='idle'&&<p className="similar-intro">이 문서의 품목을 기준으로 보관함을 살펴봅니다. API 설정 없이 사용할 수 있어요.</p>}
    {(phase==='loading'||phase==='comparing')&&<p role="status" className="similar-intro">{phase==='loading'?'관련 문서를 찾는 중이에요.':'저장된 품목과 조건을 비교하는 중이에요.'}</p>}
    {error&&<p role="alert" className="similar-error">{error}</p>}
    {phase!=='idle'&&phase!=='loading'&&!candidates.length&&!error&&<p className="similar-intro">품목이 맞는 후보가 없어요. 다른 견적서를 등록하거나 품목명·규격을 확인해 주세요.</p>}
    {!!candidates.length&&<div className="similar-candidates"><h3>비교 문서 선택</h3>{candidates.map(candidate=><button key={candidate.id} className={`similar-candidate ${report?.past.id===candidate.id?'active':''}`} onClick={()=>choose(candidate.id)} disabled={phase==='comparing'}><span><strong>{candidate.source_name||candidate.project_name||'문서명 미기재'}</strong><small>{date(candidate.issue_date)} · {candidate.chronology==='past'?'작성일 기준 과거 문서':'작성일 확인 필요 · 과거 여부 미확정'}</small><em>{candidate.reason} · 관련 품목 {candidate.matching_items}개</em></span><ArrowRight size={17}/></button>)}</div>}
    {report&&<div className="similar-report"><div className="similar-report-heading"><h3>비교 결과 요약</h3><p><strong>{report.past.name}</strong> → <strong>{report.current.name}</strong></p><small>{referenceLabel} → 현재 · {date(report.past.issue_date)} → {date(report.current.issue_date)}</small><p className="similar-scope">{report.scope}{report.chronology==='unconfirmed'?' 작성일이 없어 앞뒤 시점은 원본에서 확인해야 합니다.':''}</p></div><div className="similar-counts"><span>✓ 비교 가능 <strong>{report.summary.comparable}</strong></span><span>! 조건 확인 필요 <strong>{report.summary.review}</strong></span><span>× 비교 불가 <strong>{report.summary.incompatible}</strong></span></div>
    <section className="similar-attention"><h3>확인이 필요한 차이</h3>{report.rows.filter(row=>row.status!=='comparable').length?<ul>{report.rows.filter(row=>row.status!=='comparable').map((row,i)=><li key={i}><strong>{row.current?.name||row.past?.name||'품목명 미기재'}:</strong> {row.reasons[0]}</li>)}</ul>:<p>품목 조건에서 추가 확인 사항이 없습니다.</p>}{report.conditions.length>0&&<div className="similar-terms">{report.conditions.map(c=><p key={c.label}><strong>{c.label}</strong> · {referenceLabel} {c.past} → 현재 {c.current}</p>)}</div>}</section>
    <section className="similar-items"><h3>품목별 단가와 조건</h3>{report.rows.map((row,i)=>{const Icon=icons[row.status];return <article className={`similar-item ${row.status}`} key={`${row.current?.row||'p'}-${row.past?.row||'c'}-${i}`}><div className="similar-item-head"><span className={`similar-status ${row.status}`}><Icon size={16}/>{labels[row.status]}</span><strong>{row.current?.name||row.past?.name||'품목명 미기재'}</strong><small>{referenceLabel} {row.past?.row??'—'}행 → 현재 {row.current?.row??'—'}행</small></div><p className="similar-reason">{row.reasons.join(' ')}</p>{row.candidates.length>1&&row.current&&<label className="similar-match">대응 {referenceLabel} 품목 확인<select value={selected[row.current.row-1]??row.past?.row-1} onChange={e=>choose(report.past.id,{...selected,[row.current.row-1]:Number(e.target.value)})}>{row.candidates.map(index=><option key={index} value={index-1}>{index}행 · {shown(report.rows.find(r=>r.past?.row===index)?.past?.name||'원본에서 확인')}</option>)}</select><button type="button" className="button" onClick={()=>choose(report.past.id,{...selected,[row.current.row-1]:row.past.row-1})}>대응 확인</button></label>}<div className="similar-prices"><div><span>{referenceLabel} 단가</span><strong>{amount(row.past?.unit_price,report.past.currency)}</strong></div><div><span>현재 단가</span><strong>{amount(row.current?.unit_price,report.current.currency)}</strong></div>{row.status==='comparable'&&<div><span>차액 · 변화율</span><strong>{row.delta>0?'+':''}{amount(row.delta,report.current.currency)} · {row.percent==null?'계산 안 함':`${row.percent>0?'+':''}${percent(row.percent)}%`}</strong></div>}</div><details className="similar-details"><summary>규격·수량·옵션과 근거 보기</summary><div className="similar-detail-grid"><div><strong>{referenceLabel}</strong><p>규격 {shown(row.past?.specification)} · 수량 {shown(row.past?.quantity)} {shown(row.past?.unit)}</p><p>옵션 {shown(row.past?.option_group)} · {row.past?.is_component?'구성품':'주 품목'}</p><Source source={row.past_evidence}/></div><div><strong>현재</strong><p>규격 {shown(row.current?.specification)} · 수량 {shown(row.current?.quantity)} {shown(row.current?.unit)}</p><p>옵션 {shown(row.current?.option_group)} · {row.current?.is_component?'구성품':'주 품목'}</p><Source source={row.current_evidence}/></div></div></details></article>;})}</section>
    <section className="similar-evidence"><h3>상세 근거와 원본</h3><p>표시한 행 번호는 저장된 품목 순서예요. 원본의 페이지·시트·셀 정보가 저장된 경우에만 함께 표시합니다.</p><div><a href={fileURL(report.past.source_url)} target="_blank" rel="noreferrer">{referenceLabel} 원본 열기</a><a href={fileURL(report.current.source_url)} target="_blank" rel="noreferrer">현재 원본 열기</a></div></section></div>}
  </section>;
}
