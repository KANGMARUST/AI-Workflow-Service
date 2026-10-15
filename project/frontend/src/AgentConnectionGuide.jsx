import React from 'react';

export const STUDIO_AGENTS={extract:'agt_WUmdoTPSummj3uQ7Qdi6dM',review:'agt_3meY3NJetTYi7X9n8RTPpB',compare:'agt_R5gPHUeVuUoDCheCftTnDL'};
export const AGENT_ROLES={
 extract:{name:'견적아카이브_추출',purpose:'기존 견적 원본(PDF·Excel·Word·이미지)의 거래처·품목·단가·금액을 추출합니다.',location:'API 설정의 Agent ID / 작업실의 원본 재추출'},
 review:{name:'견적아카이브_검토',purpose:'저장된 견적 1~5건의 누락·금액 불일치·조건을 문서별로 검토합니다.',location:'작업실 → 누락·금액·조건 검토 → Agent ID'},
 compare:{name:'견적아카이브_비교',purpose:'저장된 견적 2~5건의 품목·단가·조건 차이를 비교합니다.',location:'작업실 → 여러 견적 비교 → Agent ID'},
};

export default function AgentConnectionGuide(){
 return <section className="panel agent-connection-guide" aria-labelledby="agent-connection-title">
  <div className="panel-title"><div><h2 id="agent-connection-title">어떤 에이전트를 연결하나요?</h2><p>API 설정의 Agent ID에는 <strong>견적아카이브_추출</strong>을 입력하세요. 검토·비교 Agent ID는 에이전트 작업실에서 입력합니다.</p></div></div>
  <div className="agent-connection-body">
   <dl className="connection-terms">
    <div><dt>Upstage API Key</dt><dd>본인 Upstage 계정에서 발급한 인증 키입니다. 추출·검토·비교 에이전트와 자연어 검색의 Solar 답변에 사용합니다.</dd></div>
    <div><dt>Agent ID</dt><dd>실행할 에이전트를 지정하는 agt_… 값입니다. 아래에서 작업에 맞는 에이전트 이름을 확인하세요.</dd></div>
    <div><dt>Config ID</dt><dd>선택한 에이전트의 저장된 설정 버전입니다. 이 프로젝트 계정은 추출 3, 검토·비교 2를 사용합니다.</dd></div>
   </dl>
   <p className="agent-table-hint">표를 좌우로 스크롤하면 입력 위치와 Agent ID·Config ID를 확인할 수 있습니다.</p>
   <div className="table-scroll"><table className="agent-connection-table"><thead><tr><th scope="col">Studio 에이전트 이름 · 용도</th><th scope="col">입력 위치</th><th scope="col">생성 계정의 Agent ID</th><th scope="col">Config ID</th></tr></thead><tbody>{Object.entries(AGENT_ROLES).map(([kind,role])=><tr key={kind}><td><strong>{role.name}</strong><p>{role.purpose}</p></td><td>{role.location}</td><td><code>{STUDIO_AGENTS[kind]}</code></td><td>{kind==='extract'?'3':'2'}</td></tr>)}</tbody></table></div>
   <p className="muted">위 ID는 이 프로젝트에서 생성한 계정 기준입니다. 다른 계정의 키를 쓰면 본인 Studio에서 같은 역할의 에이전트를 열어 Agent ID와 Config ID를 확인해 입력하세요. 작업실에서 작업을 바꿀 때마다 표시된 ID를 확인하세요.</p>
  </div>
 </section>;
}
