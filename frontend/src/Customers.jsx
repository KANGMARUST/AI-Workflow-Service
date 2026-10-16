import React, { useEffect, useMemo, useState } from 'react';
import { Building2, ChevronDown, ChevronLeft, ChevronRight, FileText, LoaderCircle, Plus, RotateCcw, Search, X } from 'lucide-react';
import './Customers.css';

const PAGE_SIZE = 10;
const prefixRaw = (import.meta.env.VITE_API_PREFIX || '/api').replace(/\/$/, '');
const API_PREFIX = prefixRaw.startsWith('/') ? prefixRaw : `/${prefixRaw}`;
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';
const demoCustomers = [
  ['㈜한빛테크', '제조업체', '김민수', '010-1234-5678', 'minsu@hanbit.co.kr', '부산광역시 강서구 명지동 123-45', '2025-04-21', '거래중', '-'],
  ['삼성전자㈜', '대기업', '이정은', '010-2345-6789', 'je@samsung.com', '경기도 수원시 영통구 삼성로 129', '2025-03-10', '거래중', '-'],
  ['㈜미래솔루션', 'IT/솔루션', '박지훈', '010-3456-7890', 'jh@future.co.kr', '서울특별시 금천구 가산디지털1로 88', '2024-11-05', '거래중', '우수거래처'],
  ['LG디스플레이㈜', '대기업', '최선영', '010-4567-8901', 'sy@lgdisplay.com', '서울특별시 영등포구 여의대로 128', '2024-08-14', '거래중', '-'],
  ['㈜현대엔지니어링', '건설업', '정우진', '010-5678-9012', 'wj@hdec.co.kr', '서울특별시 종로구 율곡로 75', '2024-06-22', '거래중', '-'],
  ['㈜선우산업', '제조업체', '이서연', '010-6789-0123', 'sy@sunwoo.co.kr', '경기도 화성시 동탄대로 635', '2024-04-18', '거래중', '-'],
  ['한울테크㈜', '제조업체', '김태호', '010-7890-1234', 'th@hanultech.co.kr', '대전광역시 유성구 테크노중앙로 55', '2024-02-05', '거래중', '-'],
  ['대성산업㈜', '제조업체', '강하늘', '010-8901-2345', 'hn@daesung.co.kr', '인천광역시 서구 가좌동 211', '2023-12-12', '거래중', '-'],
  ['에이스무역㈜', '무역업', '문지현', '010-9012-3456', 'jh@ace-trade.com', '서울특별시 중구 세종대로 14', '2023-09-01', '거래중', '-'],
  ['㈜테크원', '제조업체', '정민기', '010-1234-5670', 'mk@techone.co.kr', '충청남도 천안시 서북구 1공단', '2023-05-24', '휴면', '-'],
];
const demoQuotes = [
  { id: 'Q-2025-00123', date: '2025-04-21', amount: 12500000, status: 'confirmed' },
  { id: 'Q-2025-00112', date: '2025-03-10', amount: 11800000, status: 'confirmed' },
  { id: 'Q-2024-00756', date: '2024-11-05', amount: 22000000, status: 'review_required' },
];
const fmtDate = (value) => value ? String(value).slice(0, 10).replaceAll('-', '.') : '—';
const fmtMoney = (value) => `${new Intl.NumberFormat('ko-KR').format(Number(value) || 0)}원`;
const statusName = (value) => ({ confirmed: '완료', review_required: '미완료', extracting: '추출 중', rejected: '반려', archived: '보관' }[value] || '—');

async function request(path, options = {}) {
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) };
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`;
  const response = await fetch(`${API_BASE}${API_PREFIX}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? `${response.status}: ${payload.detail}` : `요청 실패 (${response.status})`);
  return payload;
}

function aggregateCustomers(quotes) {
  const map = new Map();
  quotes.forEach((quote) => {
    const name = quote.customer_name?.trim();
    if (!name) return;
    const row = map.get(name) || { id: name, name, type: '미분류', contact: quote.contact_name || '—', phone: '—', email: '—', address: '견적서에 등록된 주소 없음', recentDate: '', status: '확인 필요', note: '견적서 기준', quotes: [] };
    if (quote.contact_name && row.contact === '—') row.contact = quote.contact_name;
    if (quote.issue_date && (!row.recentDate || quote.issue_date > row.recentDate)) row.recentDate = quote.issue_date;
    row.quotes.push({ id: quote.quote_number || quote.quote_id, quoteId: quote.quote_id, date: quote.issue_date, amount: quote.total_amount, status: quote.status, currency: quote.currency });
    map.set(name, row);
  });
  return [...map.values()].map((row) => ({ ...row, quotes: row.quotes.sort((a, b) => String(b.date).localeCompare(String(a.date))) }));
}

function CustomerForm({ initial, onClose, onSave }) {
  const [form, setForm] = useState(initial || { name: '', type: '제조업체', contact: '', phone: '', email: '', address: '', note: '', status: '거래중' });
  const update = (key) => (event) => setForm((old) => ({ ...old, [key]: event.target.value }));
  return <div className="customer-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="customer-modal" role="dialog" aria-modal="true" aria-labelledby="customer-modal-title">
    <header><div><span className="eyebrow">CUSTOMER PROFILE</span><h2 id="customer-modal-title">{initial ? '거래처 정보 수정' : '거래처 등록'}</h2></div><button className="customer-icon-button" aria-label="닫기" onClick={onClose}><X /></button></header>
    <form onSubmit={(event) => { event.preventDefault(); if (form.name.trim()) onSave({ ...form, name: form.name.trim() }); }}>
      <label>거래처명 *<input required value={form.name} onChange={update('name')} placeholder="회사명을 입력하세요" /></label>
      <div className="customer-form-grid"><label>거래처 유형<select value={form.type} onChange={update('type')}>{['제조업체', '대기업', 'IT/솔루션', '건설업', '무역업', '기타'].map((item) => <option key={item}>{item}</option>)}</select></label><label>상태<select value={form.status} onChange={update('status')}><option>거래중</option><option>휴면</option></select></label></div>
      <div className="customer-form-grid"><label>담당자<input value={form.contact} onChange={update('contact')} placeholder="담당자명" /></label><label>연락처<input value={form.phone} onChange={update('phone')} placeholder="010-0000-0000" /></label></div>
      <label>이메일<input type="email" value={form.email} onChange={update('email')} placeholder="name@company.co.kr" /></label><label>주소<input value={form.address} onChange={update('address')} placeholder="주소를 입력하세요" /></label><label>비고<input value={form.note} onChange={update('note')} placeholder="메모" /></label>
      <footer><button type="button" className="secondary-button" onClick={onClose}>취소</button><button className="primary-button" type="submit">저장</button></footer>
    </form>
  </section></div>;
}

export default function Customers({ onNotify }) {
  const [vendors, setVendors] = useState([]);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('전체');
  const [statusFilter, setStatusFilter] = useState('전체');
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState('');
  const [modal, setModal] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    request('/search', { method: 'POST', signal: controller.signal, body: JSON.stringify({ kind: 'archive', limit: 100, offset: 0 }) })
      .then((data) => { setVendors(aggregateCustomers(data.items || [])); setDemo(false); })
      .catch((reason) => { if (reason.name !== 'AbortError') { setVendors(demoCustomers.map(([name, type, contact, phone, email, address, recentDate, status, note], index) => ({ id: `demo-${index}`, name, type, contact, phone, email, address, recentDate, status, note, quotes: index === 0 ? demoQuotes : [] }))); setDemo(true); setError(reason.message || '거래처 이력을 불러오지 못했습니다.'); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry]);

  const filtered = useMemo(() => vendors.filter((vendor) => `${vendor.name} ${vendor.contact} ${vendor.phone} ${vendor.email}`.toLowerCase().includes(query.trim().toLowerCase()) && (typeFilter === '전체' || vendor.type === typeFilter) && (statusFilter === '전체' || vendor.status === statusFilter)).sort((a, b) => String(b.recentDate).localeCompare(String(a.recentDate))), [vendors, query, typeFilter, statusFilter]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageVendors = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const selected = filtered.find((vendor) => vendor.id === selectedId) || pageVendors[0] || null;
  const quotes = selected?.quotes || [];
  const recentCutoff = new Date(); recentCutoff.setMonth(recentCutoff.getMonth() - 1);
  const quarterCutoff = new Date(); quarterCutoff.setMonth(quarterCutoff.getMonth() - 3);
  const recentMonth = quotes.filter((quote) => quote.date && new Date(quote.date) >= recentCutoff).length;
  const recentQuarter = quotes.filter((quote) => quote.date && new Date(quote.date) >= quarterCutoff).length;
  const totalAmount = quotes.reduce((sum, quote) => sum + Number(quote.amount || 0), 0);

  const saveVendor = (vendor) => {
    if (modal?.initial) setVendors((items) => items.map((item) => item.id === modal.initial.id ? { ...item, ...vendor } : item));
    else { const created = { ...vendor, id: `local-${Date.now()}`, recentDate: '', quotes: [] }; setVendors((items) => [created, ...items]); setSelectedId(created.id); }
    setModal(null);
    onNotify?.(demo ? '화면 예시에 거래처 정보를 반영했습니다.' : '현재 백엔드는 거래처 저장 기능을 제공하지 않아 이 화면에서만 반영됩니다.');
  };
  const resetFilters = () => { setQuery(''); setTypeFilter('전체'); setStatusFilter('전체'); setPage(0); };

  return <section className="customers-page">
    <div className="customers-heading"><button className="primary-button customer-add-button" onClick={() => setModal({ initial: null })}><Plus />거래처 등록</button></div>
    {error && <div className="customer-api-notice" role="status"><span>{demo ? '백엔드에 연결하지 못해 시안 예시 데이터를 표시 중입니다.' : error}</span><button onClick={() => setRetry((value) => value + 1)}>다시 연결</button></div>}
    <form className="panel customer-filters" onSubmit={(event) => { event.preventDefault(); setPage(0); }}><label className="customer-search"><span className="customer-search-input"><Search /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder="거래처명, 담당자, 연락처로 검색하세요." /></span></label><label>거래처 유형<span className="customer-select"><select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setPage(0); }}><option>전체</option>{[...new Set(vendors.map((vendor) => vendor.type))].filter((value) => value && value !== '미분류').sort().map((value) => <option key={value}>{value}</option>)}</select><ChevronDown /></span></label><label>상태<span className="customer-select"><select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(0); }}><option>전체</option><option>거래중</option><option>휴면</option><option>확인 필요</option></select><ChevronDown /></span></label><button type="button" className="customer-reset" onClick={resetFilters}><RotateCcw />초기화</button></form>
    <div className="customers-layout"><section className="panel customers-list"><header><h2>거래처 목록 <small>총 {loading ? '…' : `${filtered.length}${vendors.length === 100 && !demo ? '+' : ''}개`}</small></h2></header><div className="customer-table-scroll"><table><thead><tr><th className="check-col"><input aria-label="현재 페이지 전체 선택" type="checkbox" checked={pageVendors.length > 0 && pageVendors.every((vendor) => vendor.selected)} onChange={(event) => setVendors((items) => items.map((vendor) => pageVendors.some((row) => row.id === vendor.id) ? { ...vendor, selected: event.target.checked } : vendor))} /></th><th>거래처명 ↓</th><th>거래처 유형</th><th>담당자</th><th>연락처</th><th>이메일</th><th>최근 견적일</th><th>상태</th><th>비고</th></tr></thead><tbody>{pageVendors.map((vendor) => <tr key={vendor.id} className={selected?.id === vendor.id ? 'selected' : ''} onClick={() => setSelectedId(vendor.id)}><td className="check-col" onClick={(event) => event.stopPropagation()}><input aria-label={`${vendor.name} 선택`} type="checkbox" checked={Boolean(vendor.selected)} onChange={(event) => setVendors((items) => items.map((item) => item.id === vendor.id ? { ...item, selected: event.target.checked } : item))} /></td><td className="customer-name-cell">{vendor.name}</td><td>{vendor.type}</td><td>{vendor.contact || '—'}</td><td>{vendor.phone || '—'}</td><td>{vendor.email || '—'}</td><td>{fmtDate(vendor.recentDate)}</td><td><span className={`vendor-status ${vendor.status === '거래중' ? 'active' : vendor.status === '휴면' ? 'dormant' : ''}`}>{vendor.status || '확인 필요'}</span></td><td>{vendor.note || '—'}</td></tr>)}</tbody></table>{loading && <div className="customer-empty"><LoaderCircle className="spin" />거래처 이력을 불러오고 있습니다.</div>}{!loading && pageVendors.length === 0 && <div className="customer-empty">조건에 맞는 거래처가 없습니다.</div>}</div><footer className="customer-pagination"><span>페이지당 <select disabled><option>10개</option></select></span><div><button disabled={page === 0} aria-label="이전 페이지" onClick={() => setPage((value) => Math.max(0, value - 1))}><ChevronLeft /></button><b>{page + 1}</b><span>/ {pageCount}</span><button disabled={page + 1 >= pageCount} aria-label="다음 페이지" onClick={() => setPage((value) => value + 1)}><ChevronRight /></button></div></footer></section>
      <aside className="customer-side"><section className="panel customer-detail"><header><h2>거래처 상세 정보</h2><button className="customer-edit" disabled={!selected} onClick={() => setModal({ initial: selected })}>✎ 수정</button></header>{selected ? <><div className="customer-profile"><span className="customer-building"><Building2 /></span><div><b>{selected.name}</b><span>{selected.type}</span><p>{selected.description || (demo ? '거래처 등록 정보를 확인하고 견적 이력을 관리하세요.' : '등록된 거래처 프로필을 확인할 수 없습니다.')}</p></div></div><dl><div><dt>담당자</dt><dd>{selected.contact || '—'}</dd></div><div><dt>연락처</dt><dd>{selected.phone || '—'}</dd></div><div><dt>이메일</dt><dd>{selected.email || '—'}</dd></div><div><dt>주소</dt><dd>{selected.address || '—'}</dd></div><div><dt>최근 견적일</dt><dd>{fmtDate(selected.recentDate)}</dd></div><div><dt>상태</dt><dd><span className={`vendor-status ${selected.status === '거래중' ? 'active' : ''}`}>{selected.status || '확인 필요'}</span></dd></div></dl></> : <div className="customer-empty">거래처를 선택하세요.</div>}</section>
        <section className="panel customer-summary"><header><h2>견적 이력 요약</h2><button disabled={!quotes.length} onClick={() => onNotify?.('견적서 목록에서 해당 거래처를 검색해 확인하세요.')}>전체보기 <ChevronRight /></button></header><div className="customer-stats"><div><small>총 견적 수</small><b>{quotes.length}<i>건</i></b></div><div><small>최근 1개월</small><b>{recentMonth}<i>건</i></b></div><div><small>최근 3개월</small><b>{recentQuarter}<i>건</i></b></div><div><small>총 거래 금액</small><b>{fmtMoney(totalAmount)}</b></div></div></section>
        <section className="panel customer-quotes"><header><h2>최근 견적서</h2><button disabled={!quotes.length} onClick={() => onNotify?.('견적서 목록에서 해당 거래처를 검색해 확인하세요.')}>전체보기 <ChevronRight /></button></header>{quotes.length ? <div>{quotes.slice(0, 3).map((quote) => <article key={quote.quoteId || quote.id}><b>{quote.id}</b><span>{fmtDate(quote.date)}</span><span>{fmtMoney(quote.amount)}</span><em className={quote.status === 'confirmed' ? 'done' : ''}>{statusName(quote.status)}</em></article>)}</div> : <div className="customer-empty compact"><FileText />견적 이력이 없습니다.</div>}</section>
      </aside></div>
    {demo && <p className="customer-demo-caption">시안 예시 데이터 · 실제 거래처 정보가 아닙니다.</p>}
    {modal && <CustomerForm initial={modal.initial} onClose={() => setModal(null)} onSave={saveVendor} />}
  </section>;
}
