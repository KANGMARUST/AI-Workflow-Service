import React, { useMemo, useState } from 'react';
import {
  BarChart3, Box, Building2, CalendarDays, Check, CheckCircle2, ChevronDown,
  ChevronRight, Clock3, FileText, Home, MoreVertical, Plus, Search, Settings,
  UserRound, X, UploadCloud, ArrowRight,
} from 'lucide-react';

const seed = [
  { id: 'Q-2026-00148', client: '㈜한빛테크', date: '2026. 10. 14', amount: 12500000, status: '검토 미완료', title: '산업용 센서 모듈 공급 견적' },
  { id: 'Q-2026-00147', client: '삼성전자㈜', date: '2026. 10. 13', amount: 5300000, status: '검토 완료', title: '자동화 설비 부품 견적서' },
  { id: 'Q-2026-00146', client: '㈜미래솔루션', date: '2026. 10. 11', amount: 8750000, status: '검토 완료', title: '컨트롤 패널 및 부속품' },
  { id: 'Q-2026-00145', client: 'LG디스플레이㈜', date: '2026. 10. 09', amount: 21000000, status: '검토 미완료', title: '디스플레이 부품 공급 견적' },
  { id: 'Q-2026-00144', client: '㈜현대엔지니어링', date: '2026. 10. 06', amount: 4200000, status: '검토 완료', title: '정밀 가공 부품 단가 제안' },
];

const money = (value) => `${new Intl.NumberFormat('ko-KR').format(value)}원`;
const navItems = [
  { label: '홈', icon: Home }, { label: '견적서 목록', icon: FileText },
  { label: '단가 비교', icon: BarChart3 }, { label: '거래처 관리', icon: UserRound },
  { label: '품목 관리', icon: Box }, { label: '통계', icon: BarChart3 },
  { label: '설정', icon: Settings },
];

export default function App() {
  const [quotes, setQuotes] = useState(seed);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('전체');
  const [upload, setUpload] = useState(false);
  const [file, setFile] = useState('');
  const [toast, setToast] = useState('');
  const [activeNav, setActiveNav] = useState('홈');
  const [checked, setChecked] = useState([]);
  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600); };
  const rows = useMemo(() => quotes.filter((quote) =>
    `${quote.id} ${quote.client} ${quote.title}`.toLowerCase().includes(query.toLowerCase()) &&
    (filter === '전체' || quote.status === filter)), [quotes, query, filter]);

  const navigate = (label) => {
    setActiveNav(label);
    if (label === '홈') { setQuery(''); setFilter('전체'); return; }
    if (label === '견적서 목록') { document.getElementById('recent-quotes')?.scrollIntoView({ behavior: 'smooth' }); return; }
    notify(`${label} 화면은 준비 중입니다.`);
  };
  const addQuote = () => {
    if (!file) { notify('먼저 견적서 파일을 선택해 주세요.'); return; }
    const quote = { id: `Q-2026-${String(149 + quotes.length - seed.length).padStart(5, '0')}`, client: '거래처 확인 필요', date: '2026. 10. 15', amount: 0, status: '검토 미완료', title: file.replace(/\.[^.]+$/, '') };
    setQuotes((current) => [quote, ...current]); setUpload(false); setFile(''); notify('견적서가 목록에 추가되었습니다.');
  };
  const quickActions = [
    { title: '견적서 등록', detail: 'PDF·엑셀·이미지 파일 업로드', icon: FileText, action: () => setUpload(true) },
    { title: '견적서 검색', detail: '거래처, 품목, 기간, 금액으로 검색', icon: Search, action: () => { document.getElementById('quote-search')?.focus(); document.getElementById('recent-quotes')?.scrollIntoView({ behavior: 'smooth' }); } },
    { title: '과거 단가 비교', detail: '같은 품목의 단가 이력 확인', icon: BarChart3, action: () => navigate('단가 비교') },
    { title: '거래처 관리', detail: '거래처 정보 등록 및 관리', icon: UserRound, action: () => navigate('거래처 관리') },
  ];
  const updates = quotes.slice(0, 3).map((quote) => ({ text: `${quote.id} 견적서가 ${quote.status === '검토 완료' ? '검토 완료되었습니다.' : '등록되었습니다.'}`, date: quote.date.slice(5).replaceAll(' ', '') }));

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top" onClick={() => navigate('홈')} aria-label="QuoteFlow 홈"><span className="brand-mark"><FileText /></span><span>QuoteFlow</span></a>
      <nav className="main-nav" aria-label="주 메뉴">{navItems.map(({ label, icon: Icon }) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => navigate(label)}><Icon />{label}</button>)}</nav>
      <button className="user-menu" onClick={() => notify('김담당님 계정 설정은 준비 중입니다.')}><span className="avatar">김</span><span>김담당님</span><ChevronDown /></button>
    </header>

    <main id="top" className="page-content">
      <section className="welcome-row">
        <div><h1>안녕하세요, 김담당님.</h1><p>견적서 현황을 한눈에 확인하고, 필요한 정보를 빠르게 찾아보세요.</p><span className="heading-rule" /></div>
        <button className="primary-button register-button" onClick={() => setUpload(true)}><Plus />견적서 등록</button>
      </section>

      <section className="stats-grid" aria-label="견적서 현황">
        {[
          { title: '전체 견적서', value: `${quotes.length + 119}`, icon: FileText },
          { title: '작성 중', value: '5', icon: Clock3 },
          { title: '수주 완료', value: '21', icon: CheckCircle2 },
          { title: '이번 달 등록', value: `${quotes.length + 33}`, icon: CalendarDays },
        ].map(({ title, value, icon: Icon }) => <article className="stat-card" key={title}><span className="stat-icon"><Icon /></span><div className="stat-copy"><span>{title}</span><strong>{value}<small>건</small></strong></div></article>)}
      </section>

      <section className="content-grid">
        <section className="panel recent-panel" id="recent-quotes">
          <div className="panel-heading"><h2>최근 견적서</h2><button className="text-link" onClick={() => { setActiveNav('견적서 목록'); setFilter('전체'); }}>{'전체보기'}<ArrowRight /></button></div>
          <div className="table-scroll"><table className="quotes-table"><thead><tr><th className="check-col"><input aria-label="전체 선택" type="checkbox" checked={rows.length > 0 && rows.every((row) => checked.includes(row.id))} onChange={(event) => setChecked(event.target.checked ? rows.map((row) => row.id) : [])} /></th><th>견적번호</th><th>거래처</th><th>작성일</th><th>견적 금액</th><th>진행 상태</th><th aria-label="메뉴" /></tr></thead>
            <tbody>{rows.map((quote) => <tr key={quote.id}><td className="check-col"><input aria-label={`${quote.id} 선택`} type="checkbox" checked={checked.includes(quote.id)} onChange={(event) => setChecked((current) => event.target.checked ? [...current, quote.id] : current.filter((id) => id !== quote.id))} /></td><td className="quote-id">{quote.id}</td><td className="client-name">{quote.client}</td><td>{quote.date}</td><td className="amount-cell">{quote.amount ? money(quote.amount) : '확인 필요'}</td><td><span className={`status-pill ${quote.status === '검토 완료' ? 'complete' : 'pending'}`}>{quote.status}</span></td><td><button className="row-menu" aria-label={`${quote.id} 메뉴`} onClick={() => notify(`${quote.id} · ${quote.title}`)}><MoreVertical /></button></td></tr>)}</tbody>
          </table>{rows.length === 0 && <div className="empty-state">검색 결과가 없습니다.</div>}</div>
          <div className="table-controls"><label className="search-box"><Search /><input id="quote-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="견적서 검색" /></label><select aria-label="진행 상태 필터" value={filter} onChange={(event) => setFilter(event.target.value)}><option>전체</option><option>검토 미완료</option><option>검토 완료</option></select><span>총 <b>{rows.length}</b>건</span></div>
        </section>

        <aside className="side-column">
          <section className="panel quick-panel"><div className="panel-heading"><h2>빠른 기능</h2></div><div className="quick-list">{quickActions.map(({ title, detail, icon: Icon, action }) => <button className="quick-action" key={title} onClick={action}><span className="quick-icon"><Icon /></span><span className="quick-copy"><b>{title}</b><small>{detail}</small></span><ChevronRight className="quick-chevron" /></button>)}</div></section>
          <section className="panel updates-panel"><div className="panel-heading"><h2>최근 업데이트</h2><button className="text-link" onClick={() => notify('최근 업데이트를 모두 표시하고 있습니다.')}>더보기<ArrowRight /></button></div><ul>{updates.map((item, index) => <li key={`${item.text}-${index}`}><span className="update-dot" /><span className="update-text">{item.text}</span><time>{item.date}</time></li>)}</ul></section>
        </aside>
      </section>
    </main>

    {upload && <div className="modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget) setUpload(false); }}><section className="upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title"><div className="modal-heading"><div><span>NEW QUOTATION</span><h2 id="upload-title">견적서 등록</h2><p>등록할 견적서 원본 파일을 선택하세요.</p></div><button className="close-button" onClick={() => setUpload(false)} aria-label="닫기"><X /></button></div><label className="upload-drop"><UploadCloud /><b>{file || '파일을 선택하거나 여기에 놓으세요'}</b><small>PDF, Excel, 이미지 파일</small><input type="file" accept=".pdf,.xlsx,.xls,.png,.jpg,.jpeg" onChange={(event) => setFile(event.target.files?.[0]?.name || '')} /></label><p className="modal-note">업로드와 자동 추출은 API 연동 후 사용할 수 있습니다.</p><div className="modal-actions"><button className="secondary-button" onClick={() => setUpload(false)}>취소</button><button className="primary-button" onClick={addQuote}><Plus />등록</button></div></section></div>}
    {toast && <div className="toast"><Check />{toast}</div>}
  </div>;
}
