import React,{useEffect,useState} from 'react';
import {api} from './api';
import {AGENT_ROLES,STUDIO_AGENTS} from './AgentConnectionGuide';

export {STUDIO_AGENTS} from './AgentConnectionGuide';
const labels={extract:'원본 재추출',review:'누락·금액·조건 검토',compare:'여러 견적 비교'};
export default function AgentWorkspace({quotes,settings,configure,open}){
 const [kind,setKind]=useState('review'),[selected,setSelected]=useState([]),[runs,setRuns]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [agentId,setAgentId]=useState(STUDIO_AGENTS.review),[configId,setConfigId]=useState('1');
 async function refresh(){try{setRuns(await api('/agent-runs'));}catch(e){setError(e.message);}}
 useEffect(()=>{refresh();},[]);
 function selectKind(k){setKind(k);setAgentId(k==='extract'&&settings.agentId?settings.agentId:STUDIO_AGENTS[k]);setConfigId('1');setSelected([]);setError('');}
 async function run(){setError('');setBusy(true);try{await api('/agent-runs',{method:'POST',body:JSON.stringify({kind,quote_ids:selected}),ai:{...settings,agentId,configId}});}catch(e){setError(e.message);}finally{await refresh();setBusy(false);}}
 const valid=kind==='compare'?selected.length>=2&&selected.length<=5:selected.length===1;
 return <>
 <section className="panel agent-panel"><h2>Studio 에이전트로 기존 견적을 분석하세요</h2><p>추출 → 검토 → 비교의 각 작업을 실행하고 실제 API 결과와 실행 이력을 확인합니다.</p><p>분석 결과는 별도로 보관합니다. 기존 견적의 금액과 검토 완료 상태를 자동 변경하지 않습니다.</p><a href="https://ku-sejong-hackathon-playbook.vercel.app/#sec5" target="_blank" rel="noreferrer">에이전트 사용 가이드북</a></section>
 {!settings.enabled&&<div className="info-banner"><span>본인 API를 설정하면 에이전트를 실행할 수 있습니다.</span><button className="button" onClick={configure}>API 설정</button></div>}
 <section className="panel agent-panel"><div className="agent-actions">{Object.entries(labels).map(([k,label])=><button key={k} className={'button '+(kind===k?'primary':'')} disabled={busy} onClick={()=>selectKind(k)}>{label}</button>)}</div>
 <div className="agent-role-guide" id="selected-agent-guide"><strong>연결할 Studio 에이전트: {AGENT_ROLES[kind].name}</strong><p>{AGENT_ROLES[kind].purpose}</p><p>API 설정에서 적용한 Upstage API Key를 함께 사용합니다. 아래에는 이 역할의 Agent ID와 설정 버전을 입력하세요. 생성 계정의 Config ID는 1입니다.</p><button className="text-button" onClick={configure} disabled={busy}>전체 에이전트 ID 안내 · API 설정</button></div>
 <div className="advanced-grid"><label className="field">{AGENT_ROLES[kind].name} Agent ID<input aria-describedby="selected-agent-guide" value={agentId} onChange={e=>setAgentId(e.target.value)} disabled={busy}/></label><label className="field">Config ID · 설정 버전<input type="number" min="1" value={configId} onChange={e=>setConfigId(e.target.value)} disabled={busy}/></label></div>
 <p>{kind==='compare'?'문서 2~5개를 선택하세요.':'문서 1개를 선택하세요.'}{kind==='extract'?' 원본 재추출은 PDF만 지원합니다.':' 저장 데이터의 분석 입력 PDF를 에이전트에 전송합니다.'}</p>
 <div className="agent-document-list">{quotes.map(q=><label key={q.id} className="acknowledge"><input type="checkbox" disabled={busy||(kind==='extract'&&!q.source_name.toLowerCase().endsWith('.pdf'))} checked={selected.includes(q.id)} onChange={e=>setSelected(e.target.checked?(kind==='compare'?[...selected,q.id]:[q.id]):selected.filter(i=>i!==q.id))}/><span><strong>{q.project_name||q.source_name}</strong><br/>{q.customer||'거래처 미기재'} · {q.source_name}</span></label>)}</div>
 <button className="button primary" disabled={busy||!settings.enabled||!valid||!/^agt_[A-Za-z0-9_-]{4,160}$/.test(agentId)||!/^[1-9][0-9]{0,8}$/.test(configId)} onClick={run}>{busy?'Studio 에이전트 실행 중…':labels[kind]+' 실행'}</button>{busy&&<p role="status">문서 전송 → 에이전트 실행 → 완료 상태 조회 → 결과 저장 순서로 진행합니다.</p>}{error&&<p className="validation" role="alert">{error}</p>}</section>
 <section className="panel agent-panel"><h2>실제 에이전트 실행 이력</h2>{!runs.length&&<p>아직 실행 기록이 없습니다. 로컬 분석과 모의 테스트를 API 실행 결과로 표시하지 않습니다.</p>}{runs.map(r=><article className="agent-report" key={r.id}><h3>{labels[r.kind]} · {({completed:'완료',failed:'실패',running:'진행 중'})[r.status]}</h3><small>{r.started_at} · {r.agent_id} · 설정 {r.config_id}</small><div className="agent-actions">{r.quote_ids.map(id=><button className="text-button" key={id} onClick={()=>open(id)}>{quotes.find(q=>q.id===id)?.source_name||id} · 분석 버전 {r.quote_versions[id]}</button>)}</div>{r.error&&<p className="validation">{r.error}</p>}{r.result&&<><p>{Array.isArray(r.result.summary)?r.result.summary.join(' '):r.result.summary}</p>{['risk_level','comparison_level'].map(k=>r.result[k]&&<p key={k}>{String(r.result[k])}</p>)}{['findings','recommendations','differences','limitations'].map(k=>Array.isArray(r.result[k])&&<ul key={k}>{r.result[k].map((v,i)=><li key={i}>{typeof v==='string'?v:JSON.stringify(v)}</li>)}</ul>)}<details><summary>에이전트 원본 JSON · 응답 {r.metadata?.response_id}</summary><pre className="agent-json">{JSON.stringify(r.result,null,2)}</pre></details><p className="muted">AI 분석입니다. 원본 문서와 근거를 대조해 확인해주세요.</p></>}</article>)}</section>
 </>;
}
