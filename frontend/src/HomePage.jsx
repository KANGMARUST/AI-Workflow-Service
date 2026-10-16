import React, { useMemo, useState } from 'react';
import { ArrowRight, BarChart3, ChevronRight, FileText, MoreVertical, Search, UserRound } from 'lucide-react';
import './HomePage.css';

const money = (value) => `${new Intl.NumberFormat('ko-KR').format(value)}원`;

export default function HomePage({ quotes, quotesLoading, quotesError, onNotify, onNavigate, onOpenQuote, onUpload }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('전체');
  const [checked, setChecked] = useState([]);
  const rows = useMemo(() => quotes.filter((quote) =>
    `${quote.id} ${quote.client} ${quote.title}`.toLowerCase().includes(query.toLowerCase()) &&
    (filter === '전체' || quote.status === filter)), [quotes, query, filter]);
  const quickActions = [
    { title: '견적서 등록', detail: 'PDF·XLSX 파일 업로드', icon: FileText, action: onUpload },
    { title: '견적서 검색', detail: '거래처, 품목, 기간, 금액으로 검색', icon: Search, action: () => { document.getElementById('quote-search')?.focus(); document.getElementById('recent-quotes')?.scrollIntoView({ behavior: 'smooth' }); } },
    { title: '과거 단가 비교', detail: '같은 품목의 단가 이력 확인', icon: BarChart3, action: () => onNavigate('단가 비교') },
    { title: '거래처 관리', detail: '거래처 정보 등록 및 관리', icon: UserRound, action: () => onNavigate('거래처 관리') },
  ];
  const updates = quotes.slice(0, 3).map((quote) => ({ text: `${quote.id} 견적서가 ${quote.status === '검토 완료' ? '검토 완료되었습니다.' : '등록되었습니다.'}`, date: quote.date.slice(5).replaceAll(' ', '') }));

  const renderRows = () => rows.map((quote) => <tr key={quote.id} className="home-quote-row" tabIndex={0} onClick={() => onOpenQuote?.(quote)} onKeyDown={(event) => { if ((event.key === 'Enter' || event.key === ' ') && !event.target.closest('button,input,a,select')) { event.preventDefault(); onOpenQuote?.(quote); } }}>
    <td className="check-col" onClick={(event) => event.stopPropagation()}><input aria-label={`${quote.id} 선택`} type="checkbox" checked={checked.includes(quote.id)} onChange={(event) => setChecked((current) => event.target.checked ? [...current, quote.id] : current.filter((id) => id !== quote.id))} /></td>
    <td className="quote-id">{quote.id}</td><td className="client-name">{quote.client}</td><td>{quote.date}</td><td className="amount-cell">{quote.amount ? money(quote.amount) : '금액 미기재'}</td>
    <td><span className={`status-pill ${quote.status === '검토 완료' ? 'complete' : 'pending'}`}>{quote.status}</span></td>
    <td><button className="row-menu" aria-label={`${quote.id} 메뉴`} onClick={(event) => { event.stopPropagation(); onNotify(quote.id); }}><MoreVertical /></button></td>
  </tr>);

  return <div className="home-page">
    <section className="welcome-row"><div><h1>안녕하세요, 김담당님.</h1><span className="heading-rule" /></div></section>
    <section className="content-grid">
      <section className="panel recent-panel" id="recent-quotes"><div className="panel-heading"><h2>최근 견적서</h2><button className="text-link" onClick={() => onNavigate('견적서 목록')}>전체보기<ArrowRight /></button></div>
        <div className="table-scroll"><table className="quotes-table"><thead><tr><th className="check-col"><input aria-label="전체 선택" type="checkbox" checked={rows.length > 0 && rows.every((row) => checked.includes(row.id))} onChange={(event) => setChecked(event.target.checked ? rows.map((row) => row.id) : [])} /></th><th>견적번호</th><th>거래처</th><th>작성일</th><th>견적 금액</th><th>진행 상태</th><th aria-label="메뉴" /></tr></thead><tbody>{renderRows()}</tbody></table>{rows.length === 0 && <div className="empty-state">{quotesLoading ? '최근 견적서를 불러오는 중입니다.' : quotesError ? `견적서를 불러오지 못했습니다. ${quotesError}` : query || filter !== '전체' ? '검색 결과가 없습니다.' : '등록된 견적서가 없습니다.'}</div>}</div>
        <div className="table-controls"><label className="search-box"><Search /><input id="quote-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="견적서 검색" /></label><select aria-label="진행 상태 필터" value={filter} onChange={(event) => setFilter(event.target.value)}><option>전체</option><option>검토 미완료</option><option>검토 완료</option></select><span>총 <b>{rows.length}</b>건</span></div>
      </section>
      <aside className="side-column"><section className="panel quick-panel"><div className="panel-heading"><h2>빠른 기능</h2></div><div className="quick-list">{quickActions.map(({ title, detail, icon: Icon, action }) => <button className="quick-action" key={title} onClick={action}><span className="quick-icon"><Icon /></span><span className="quick-copy"><b>{title}</b><small>{detail}</small></span><ChevronRight className="quick-chevron" /></button>)}</div></section>
        <section className="panel updates-panel"><div className="panel-heading"><h2>최근 업데이트</h2><button className="text-link" onClick={() => onNotify('최근 업데이트를 모두 표시하고 있습니다.')}>더보기<ArrowRight /></button></div><ul>{updates.map((item, index) => <li key={`${item.text}-${index}`}><span className="update-dot" /><span className="update-text">{item.text}</span><time>{item.date}</time></li>)}</ul></section>
      </aside>
    </section>
  </div>;
}
