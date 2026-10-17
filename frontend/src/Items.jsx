import React, { useEffect, useMemo, useState } from 'react';
import { Box, ChevronDown, ChevronLeft, ChevronRight, LoaderCircle, Plus, RotateCcw, Search, X } from 'lucide-react';
import './Items.css';

const PAGE_SIZE = 10;
const rawPrefix = (import.meta.env.VITE_API_PREFIX || '/api').replace(/\/$/, '');
const API_PREFIX = rawPrefix.startsWith('/') ? rawPrefix : `/${rawPrefix}`;
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';
const fmtDate = (value) => value ? String(value).slice(0, 10).replaceAll('-', '.') : '—';
const fmtPrice = (value) => value == null || value === '' ? '—' : new Intl.NumberFormat('ko-KR').format(Number(String(value).replaceAll(',', '')) || 0);
const formatDetails = (value) => String(value || '')
  .split(/\s*-\.\s*/)
  .flatMap((part) => part
    .replace(/,\s*(?=(?:명암비\s|HDMI(?:\s|×)|스위블\s*[,]))/gi, '\n')
    .replace(/\s+(?=(?:SSD|HDD|Display|O\/S|Warranty)\s*:)/gi, '\n')
    .replace(/\s*\.\s*(?=HDMI\s+\d+\s*M?\s*케이블)/gi, '\n')
    .split('\n'))
  .map((line) => line.trim().replace(/^[,;]+|[,;]+$/g, '').trim())
  .filter(Boolean);

async function api(path, options = {}) {
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) };
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`;
  const response = await fetch(`${API_BASE}${API_PREFIX}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? `${response.status}: ${payload.detail}` : `요청 실패 (${response.status})`);
  return payload;
}

function groupQuoteItems(quotes) {
  const grouped = new Map();
  quotes.forEach((quote) => (quote.items || []).forEach((line) => {
    const name = String(line.item_name || '').trim();
    if (!name) return;
    const spec = line.specification || '';
    const unit = line.unit || '';
    const key = `${name}\u0000${spec}\u0000${unit}`;
    const history = { date: quote.issue_date, customer: quote.customer_name || '거래처 미기재', price: line.unit_price, quantity: line.quantity, quote: quote.quote_number || quote.quote_id, quoteId: quote.quote_id, status: quote.status, currency: line.currency || quote.currency };
    const item = grouped.get(key) || { id: key, name, spec, category: '미분류', unit: unit || '—', price: null, recentDate: '', customers: new Set(), status: '정보 미등록', description: '', createdDate: '', updatedDate: '', registeredBy: '—', history: [] };
    item.history.push(history);
    item.customers.add(history.customer);
    if (quote.issue_date && (!item.recentDate || quote.issue_date > item.recentDate)) {
      item.recentDate = quote.issue_date;
      item.price = line.unit_price;
      item.currency = history.currency;
    }
    if (quote.created_at && (!item.createdDate || quote.created_at < item.createdDate)) item.createdDate = quote.created_at.slice(0, 10);
    if (quote.updated_at && (!item.updatedDate || quote.updated_at > item.updatedDate)) item.updatedDate = quote.updated_at.slice(0, 10);
    grouped.set(key, item);
  }));
  return [...grouped.values()].map((item) => ({ ...item, customers: item.customers.size, history: item.history.sort((a, b) => String(b.date).localeCompare(String(a.date))) }));
}

function ItemForm({ initial, onClose, onSave }) {
  const [form, setForm] = useState(initial || { name: '', spec: '', category: '자동화 부품', unit: 'EA', description: '', status: '사용중' });
  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  return <div className="item-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="item-modal" role="dialog" aria-modal="true" aria-labelledby="item-form-title"><header><div><span className="eyebrow">ITEM CATALOG</span><h2 id="item-form-title">{initial ? '품목 정보 수정' : '품목 등록'}</h2></div><button className="item-icon-close" aria-label="닫기" onClick={onClose}><X /></button></header><form onSubmit={(event) => { event.preventDefault(); if (form.name.trim()) onSave({ ...form, name: form.name.trim() }); }}>
    <label>품목명 *<input required value={form.name} onChange={update('name')} placeholder="품목명을 입력하세요" /></label>
    <div className="item-form-grid"><label>규격 / 모델명<input value={form.spec} onChange={update('spec')} placeholder="예: JIG-A100" /></label><label>분류<select value={form.category} onChange={update('category')}>{['자동화 부품', '전기/전자 부품', '구조재', '구동 부품', '전달 부품', '기타'].map((v) => <option key={v}>{v}</option>)}</select></label></div>
    <div className="item-form-grid"><label>단위<input value={form.unit} onChange={update('unit')} placeholder="EA" /></label><label>상태<select value={form.status} onChange={update('status')}><option>사용중</option><option>미사용</option></select></label></div>
    <label>설명<input value={form.description} onChange={update('description')} placeholder="품목 설명" /></label><footer><button type="button" className="secondary-button" onClick={onClose}>취소</button><button className="primary-button">저장</button></footer>
  </form></section></div>;
}

export default function Items({ onNotify, onOpenQuote, refreshKey = 0 }) {
  const [items, setItems] = useState([]);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('전체');
  const [unit, setUnit] = useState('전체');
  const [customer, setCustomer] = useState('전체');
  const [sort, setSort] = useState('최근 등록순');
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState('');
  const [modal, setModal] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    api('/search', { method: 'POST', signal: controller.signal, body: JSON.stringify({ kind: 'archive', limit: 100, offset: 0 }) })
      .then(async (data) => {
        const details = await Promise.all((data.items || []).map(async (quote) => { try { return await api(`/quotes/${encodeURIComponent(quote.quote_id)}`, { signal: controller.signal }); } catch (reason) { if (reason.name === 'AbortError') throw reason; return null; } }));
        if (controller.signal.aborted) return;
        const catalog = groupQuoteItems(details.filter(Boolean));
        setItems(catalog); setDemo(false);
      })
      .catch((reason) => { if (reason.name !== 'AbortError') { setItems(demoItems.map(([name, spec, category, unit, price, recentDate, customers, status, description], index) => ({ id: `demo-${index}`, name, spec, category, unit, price, recentDate, customers, status, description, createdDate: '2023-05-12', updatedDate: recentDate, registeredBy: '김담당', currency: 'KRW', history: index === 0 ? demoHistory : [] }))); setDemo(true); setError(reason.message || '품목 정보를 불러오지 못했습니다.'); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry, refreshKey]);

  const categories = [...new Set(items.map((item) => item.category).filter(Boolean))];
  const units = [...new Set(items.map((item) => item.unit).filter(Boolean))];
  const customers = [...new Set(items.flatMap((item) => item.history.map((row) => row.customer)).filter(Boolean))].sort();
  const filtered = useMemo(() => items.filter((item) => `${item.name} ${item.spec}`.toLowerCase().includes(search.trim().toLowerCase()) && (category === '전체' || item.category === category) && (unit === '전체' || item.unit === unit) && (customer === '전체' || item.history.some((row) => row.customer === customer))).sort((a, b) => sort === '품목명순' ? a.name.localeCompare(b.name, 'ko') : String(b.recentDate).localeCompare(String(a.recentDate))), [items, search, category, unit, customer, sort]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const selected = filtered.find((item) => item.id === selectedId) || filtered[0] || null;
  const selectedDetails = formatDetails(selected?.spec);
  const visibleHistory = selected?.history || [];
  const reset = () => { setSearch(''); setCategory('전체'); setUnit('전체'); setCustomer('전체'); setPage(0); };
  const saveItem = (value) => {
    if (modal?.initial) setItems((current) => current.map((item) => item.id === modal.initial.id ? { ...item, ...value, updatedDate: new Date().toISOString().slice(0, 10) } : item));
    else { const newItem = { ...value, id: `local-${Date.now()}`, price: null, recentDate: '', customers: 0, history: [], createdDate: new Date().toISOString().slice(0, 10), updatedDate: new Date().toISOString().slice(0, 10), registeredBy: '김담당' }; setItems((current) => [newItem, ...current]); setSelectedId(newItem.id); }
    setModal(null); onNotify?.(demo ? '화면 예시 목록에 품목을 반영했습니다.' : '현재 백엔드는 품목 저장 기능을 제공하지 않아 이 화면에서만 반영됩니다.');
  };

  return <section className="items-page">
    {error && <div className="item-api-notice"><span>{demo ? '백엔드에 연결하지 못해 시안 예시 데이터를 표시 중입니다.' : error}</span><button onClick={() => setRetry((value) => value + 1)}>다시 연결</button></div>}
    <form className="panel item-filters" onSubmit={(event) => { event.preventDefault(); setPage(0); }}><label className="item-search"><b>품목 검색</b><span><Search /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="품목명, 규격, 모델명으로 검색하세요." /></span></label><label><b>품목 분류</b><span className="item-select"><select value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }}><option>전체</option>{categories.filter((value) => value !== '미분류').map((value) => <option key={value}>{value}</option>)}</select><ChevronDown /></span></label><label><b>단위</b><span className="item-select"><select value={unit} onChange={(event) => { setUnit(event.target.value); setPage(0); }}><option>전체</option>{units.filter((value) => value !== '—').map((value) => <option key={value}>{value}</option>)}</select><ChevronDown /></span></label><label><b>거래처</b><span className="item-select"><select value={customer} onChange={(event) => { setCustomer(event.target.value); setPage(0); }}><option>전체</option>{customers.map((value) => <option key={value}>{value}</option>)}</select><ChevronDown /></span></label><div className="item-filter-actions"><button type="button" className="item-reset" onClick={reset}><RotateCcw />초기화</button><button type="button" className="primary-button item-add-button" onClick={() => setModal({ initial: null })}><Plus />품목 등록</button></div></form>
    <div className={`items-layout ${selected ? 'has-selection' : ''}`}><section className="panel item-list"><header><h2>품목 목록 <small>총 {loading ? '…' : `${demo ? 128 : filtered.length}${demo ? '건' : '건'}`}</small></h2><label className="item-sort"><select value={sort} onChange={(event) => setSort(event.target.value)}><option>최근 등록순</option><option>품목명순</option></select><ChevronDown /></label></header><div className="item-table-scroll"><table><thead><tr><th className="check-col"><input aria-label="현재 페이지 전체 선택" onChange={(event) => setItems((current) => current.map((item) => pageItems.some((row) => row.id === item.id) ? { ...item, selected: event.target.checked } : item))} type="checkbox" /></th><th>품목명</th><th>최근 거래일</th><th>거래처</th><th /></tr></thead><tbody>{pageItems.map((item) => <tr key={item.id} className={selected?.id === item.id ? 'selected' : ''} onClick={() => setSelectedId(item.id)}><td className="check-col" onClick={(event) => event.stopPropagation()}><input type="checkbox" aria-label={`${item.name} 선택`} checked={Boolean(item.selected)} onChange={(event) => setItems((current) => current.map((row) => row.id === item.id ? { ...row, selected: event.target.checked } : row))} /></td><td className="item-name-cell">{item.name}</td><td>{fmtDate(item.history[0]?.date || item.recentDate)}</td><td>{item.history[0]?.customer || '—'}</td><td><button className="item-row-menu" aria-label={`${item.name} 수정`} onClick={(event) => { event.stopPropagation(); setModal({ initial: item }); }}>···</button></td></tr>)}</tbody></table>{loading && <div className="item-empty"><LoaderCircle className="spin" />품목 이력을 불러오는 중입니다.</div>}{!loading && pageItems.length === 0 && <div className="item-empty">조건에 맞는 품목이 없습니다.</div>}</div><footer className="item-pagination"><span>페이지당 <select disabled><option>10개</option></select></span><div><button disabled={page === 0} aria-label="이전 페이지" onClick={() => setPage((value) => Math.max(0, value - 1))}><ChevronLeft /></button><b>{page + 1}</b><span>/ {pageCount}</span><button disabled={page + 1 >= pageCount} aria-label="다음 페이지" onClick={() => setPage((value) => value + 1)}><ChevronRight /></button></div><small>총 {demo ? '128' : filtered.length}건</small></footer></section>
      {selected && <aside className="item-side"><section className="panel item-detail"><header><h2>품목 상세 정보</h2><button className="item-edit-button" onClick={() => setModal({ initial: selected })}>✎ 수정</button></header><div className="item-profile"><span><Box /></span><div><b>{selected.name}</b><em className={selected.status === '사용중' ? 'active' : ''}>{selected.status}</em><small>{selectedDetails.length ? selectedDetails.map((line, index) => <React.Fragment key={`${index}-${line}`}>{index > 0 && <br />}{line}</React.Fragment>) : '세부 사항 미기재'}</small></div></div><dl><div><dt>품목 분류</dt><dd>{selected.category}</dd><dt>최초 등록일</dt><dd>{fmtDate(selected.createdDate)}</dd></div><div><dt>단위</dt><dd>{selected.unit}</dd><dt>최근 수정일</dt><dd>{fmtDate(selected.updatedDate || selected.recentDate)}</dd></div><div><dt>세부 사항</dt><dd>{selectedDetails.length ? selectedDetails.map((line, index) => <React.Fragment key={`${index}-${line}`}>{index > 0 && <br />}{line}</React.Fragment>) : '—'}</dd><dt>거래처 수</dt><dd>{selected.customers}개</dd></div><div><dt>설명</dt><dd>{selected.description || '등록된 설명이 없습니다.'}</dd><dt>등록자</dt><dd>{selected.registeredBy || '—'}</dd></div></dl><section className="item-history"><header><h3>최근 단가 이력</h3><button onClick={() => onNotify?.('단가 비교 화면에서 품목 이력을 더 자세히 볼 수 있습니다.')}>전체보기 <ChevronRight /></button></header><div className="item-history-scroll"><table><thead><tr><th>작성일</th><th>거래처</th><th>단가(원)</th><th>수량</th><th>견적번호</th></tr></thead><tbody>{visibleHistory.slice(0, 5).map((row, index) => <tr key={`${row.quote}-${index}`}><td>{fmtDate(row.date)}</td><td>{row.customer}</td><td>{fmtPrice(row.price)}</td><td>{row.quantity ?? '—'}</td><td>{row.quoteId && !demo ? <button type="button" className="item-quote-link" onClick={() => onOpenQuote?.(row.quoteId, row.quote)}>{row.quote}</button> : row.quote}</td></tr>)}</tbody></table>{!visibleHistory.length && <div className="item-history-empty">이 품목의 견적 단가 이력이 없습니다.</div>}</div></section></section></aside>}</div>
    {demo && <p className="item-demo-caption">시안 예시 데이터 · 실제 품목 정보가 아닙니다.</p>}
    {modal && <ItemForm initial={modal.initial} onClose={() => setModal(null)} onSave={saveItem} />}
  </section>;
}
