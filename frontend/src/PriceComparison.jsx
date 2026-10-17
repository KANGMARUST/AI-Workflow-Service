import React, { useEffect, useMemo, useState } from 'react';
import {
  CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Download,
  FileSpreadsheet, Filter, LoaderCircle, Plus, Search,
} from 'lucide-react';
import './PriceComparison.css';

const PAGE_SIZE = 10;
const apiPrefixRaw = (import.meta.env.VITE_API_PREFIX || '/api').replace(/\/$/, '');
const API_PREFIX = apiPrefixRaw.startsWith('/') ? apiPrefixRaw : `/${apiPrefixRaw}`;
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';

const statusLabels = { confirmed: '완료', review_required: '미완료', extracting: '추출 중', rejected: '반려', archived: '보관' };
const formatInteger = (value) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const formatPrice = (value, currency) => {
  if (value === null || value === undefined || value === '') return '미기재';
  const [integer, fraction] = String(value).split('.');
  const result = fraction ? `${formatInteger(integer)}.${fraction}` : formatInteger(integer);
  return currency === 'KRW' ? `${result}원` : currency ? `${result} ${currency}` : result;
};
const formatDate = (value) => value ? value.slice(0, 10).replaceAll('-', '. ') : '날짜 미기재';
const formatDetails = (value) => String(value || '세부 사항 미기재')
  .split(/\s*-\.\s*/)
  .flatMap((part) => part
    .replace(/,\s*(?=(?:명암비\s|HDMI(?:\s|×)|스위블\s*[,]))/gi, '\n')
    .replace(/\s+(?=(?:SSD|HDD|Display|O\/S|Warranty)\s*:)/gi, '\n')
    .replace(/\s*\.\s*(?=HDMI\s+\d+\s*M?\s*케이블)/gi, '\n')
    .split('\n'))
  .map((line) => line.trim().replace(/^[,;]+|[,;]+$/g, '').trim())
  .filter(Boolean);
const normalizeRow = (row, index) => ({
  itemId: row.item_id || `${row.quote_id}-${row.line_number ?? index}`,
  itemName: row.item_name || '품목명 미기재',
  specification: row.specification || '규격 미기재',
  unit: row.unit || '미기재',
  customer: row.customer_name || '거래처 미기재',
  date: row.issue_date ? String(row.issue_date).slice(0, 10) : '',
  quantity: row.quantity == null ? '' : String(row.quantity),
  unitPrice: row.unit_price == null ? null : String(row.unit_price),
  currency: row.currency || '',
  amount: row.amount == null ? null : String(row.amount),
  quoteId: row.quote_id,
  quoteNumber: row.quote_number || row.quote_id,
  lineNumber: row.line_number,
  status: row.status || '',
});

async function apiJson(path, options = {}) {
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) };
  if (API_TOKEN) headers.Authorization = `Bearer ${API_TOKEN}`;
  const response = await fetch(`${API_BASE}${API_PREFIX}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload.detail === 'string' ? payload.detail : '요청을 처리하지 못했습니다.';
    throw new Error(`${response.status}: ${message}`);
  }
  return payload;
}

function exactPriceRows(rows, selected) {
  if (!selected) return [];
  return rows.filter((row) => row.itemName === selected.itemName && row.specification === selected.specification && row.unit === selected.unit && row.currency === selected.currency && row.unitPrice !== null);
}

function toScaledPrice(value) {
  const [whole, fraction = ''] = String(value).split('.');
  return BigInt(whole) * 10000n + BigInt(fraction.padEnd(4, '0').slice(0, 4) || '0');
}

function averagePrice(values) {
  if (!values.length) return null;
  const total = values.reduce((sum, value) => sum + toScaledPrice(value), 0n);
  const rounded = (total + BigInt(values.length) / 2n) / BigInt(values.length);
  const whole = rounded / 10000n;
  const fraction = String(rounded % 10000n).padStart(4, '0').replace(/0+$/, '');
  return fraction ? `${whole}.${fraction}` : String(whole);
}

function downloadHistory(rows) {
  const columns = [
    ['품목명', 'itemName'], ['세부 사항', 'specification'], ['단위', 'unit'],
    ['거래처', 'customer'], ['작성일', 'date'], ['수량', 'quantity'],
    ['단가', 'unitPrice'], ['통화', 'currency'], ['금액', 'amount'], ['견적번호', 'quoteId'],
  ];
  const cell = (value) => {
    let text = String(value ?? '');
    if (/^\s*[=+\-@]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  };
  const csv = [columns.map(([label]) => cell(label)).join(','), ...rows.map((row) => columns.map(([, key]) => cell(row[key])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = '모두의-견적서-단가-이력.csv'; anchor.click();
  URL.revokeObjectURL(url);
}

function StatCard({ label, value, currency }) {
  return <div className="price-stat"><small>{label}</small><b>{value == null ? '—' : formatPrice(value, currency)}</b></div>;
}

function PriceTrend({ rows }) {
  const values = rows.map((row) => Number(row.unitPrice)).filter(Number.isFinite);
  if (!values.length) return <div className="trend-empty">비교할 단가 이력이 없습니다.</div>;
  const width = 440; const height = 150; const left = 48; const right = 12; const top = 12; const bottom = 28;
  const min = Math.min(...values); const max = Math.max(...values); const spread = max - min || max * 0.12 || 1;
  const low = min - spread * 0.12; const high = max + spread * 0.12;
  const x = (index) => left + (values.length === 1 ? (width - left - right) / 2 : index * (width - left - right) / (values.length - 1));
  const y = (value) => top + (high - value) * (height - top - bottom) / (high - low);
  const points = values.map((value, index) => `${x(index)},${y(value)}`).join(' ');
  const ticks = [0, 1, 2, 3].map((index) => high - index * (high - low) / 3);
  const labels = rows.map((row) => row.date ? `${row.date.slice(2, 4)}.${row.date.slice(5, 7)}` : '—');
  return <div className="trend-chart">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="선택 품목의 과거 단가 추이">
      {ticks.map((tick, index) => <g key={index}><line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} className="chart-grid" /><text x={left - 8} y={y(tick) + 4} textAnchor="end" className="chart-y-label">{formatInteger(Math.round(tick / 1000) * 1000)}</text></g>)}
      <polygon points={`${left},${height - bottom} ${points} ${width - right},${height - bottom}`} className="chart-fill" />
      <polyline points={points} className="chart-line" />
      {values.map((value, index) => <g key={`${value}-${index}`}><circle cx={x(index)} cy={y(value)} r="3.5" className="chart-point" /><text x={x(index)} y={height - 7} textAnchor="middle" className="chart-x-label">{labels[index]}</text></g>)}
    </svg>
  </div>;
}

export default function PriceComparison({ onNotify, onOpenQuote, refreshKey = 0 }) {
  const [keyword, setKeyword] = useState('');
  const [submittedKeyword, setSubmittedKeyword] = useState('');
  const [apiRows, setApiRows] = useState([]);
  const [apiTotal, setApiTotal] = useState(0);
  const [isDemo, setIsDemo] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [customerFilter, setCustomerFilter] = useState('전체');
  const [unitFilter, setUnitFilter] = useState('전체');
  const [currencyFilter, setCurrencyFilter] = useState('전체');
  const [periodFilter, setPeriodFilter] = useState('전체 기간');
  const [sort, setSort] = useState('최신순');
  const [page, setPage] = useState(0);
  const [selectedKey, setSelectedKey] = useState('');
  const [checkedKeys, setCheckedKeys] = useState([]);
  const [compareResult, setCompareResult] = useState(null);
  const [compareError, setCompareError] = useState('');
  const [retry, setRetry] = useState(0);
  const [applyingPrice, setApplyingPrice] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setIsDemo(false);
    const keyword = submittedKeyword.trim();
    const loadHistory = async () => {
      const allRows = [];
      let offset = 0;
      let total = 0;
      do {
        const params = new URLSearchParams({ limit: '100', offset: String(offset) });
        if (keyword) params.set('keyword', keyword);
        const data = await apiJson(`/items/history?${params}`, { signal: controller.signal });
        allRows.push(...(data.items || []));
        total = data.total || 0;
        offset += data.limit || 100;
      } while (!controller.signal.aborted && offset < total);
      if (controller.signal.aborted) return;
      setApiRows(allRows.map(normalizeRow)); setApiTotal(total); setCustomerFilter('전체'); setUnitFilter('전체'); setCurrencyFilter('전체'); setPage(0);
    };
    loadHistory()
      .catch((reason) => {
        if (reason.name !== 'AbortError') { setApiRows(demoRows); setApiTotal(demoRows.length); setIsDemo(true); setError(reason.message || '단가 이력을 불러오지 못했습니다.'); }
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [submittedKeyword, retry, refreshKey]);

  const sourceRows = apiRows || demoRows;
  const customers = useMemo(() => [...new Set(sourceRows.map((row) => row.customer).filter((value) => value && value !== '거래처 미기재'))].sort(), [sourceRows]);
  const units = useMemo(() => [...new Set(sourceRows.map((row) => row.unit).filter((value) => value && value !== '미기재'))].sort(), [sourceRows]);
  const currencies = useMemo(() => [...new Set(sourceRows.map((row) => row.currency).filter(Boolean))].sort(), [sourceRows]);
  const filteredRows = useMemo(() => {
    const cutoff = periodFilter === '전체 기간' ? null : new Date();
    if (cutoff && periodFilter !== '전체 기간') cutoff.setMonth(cutoff.getMonth() - Number(periodFilter));
    const filtered = sourceRows.filter((row) => {
      if (customerFilter !== '전체' && row.customer !== customerFilter) return false;
      if (unitFilter !== '전체' && row.unit !== unitFilter) return false;
      if (currencyFilter !== '전체' && row.currency !== currencyFilter) return false;
      if (cutoff && row.date && new Date(`${row.date}T00:00:00`) < cutoff) return false;
      return true;
    });
    return filtered.sort((a, b) => {
      if (sort === '최저 단가순') return Number(a.unitPrice ?? Infinity) - Number(b.unitPrice ?? Infinity);
      if (sort === '최고 단가순') return Number(b.unitPrice ?? -Infinity) - Number(a.unitPrice ?? -Infinity);
      return String(b.date).localeCompare(String(a.date));
    });
  }, [sourceRows, customerFilter, unitFilter, currencyFilter, periodFilter, sort]);
  const summaryRows = useMemo(() => {
    const grouped = new Map();
    filteredRows.forEach((row) => {
      const key = `${row.itemName}\u0000${row.specification}\u0000${row.unit}\u0000${row.currency}`;
      const group = grouped.get(key) || { key, itemName: row.itemName, lowest: null, latestDate: '' };
      if (row.date && row.date > group.latestDate) group.latestDate = row.date;
      if (row.unitPrice !== null && (!group.lowest || toScaledPrice(row.unitPrice) < toScaledPrice(group.lowest.unitPrice)
        || (toScaledPrice(row.unitPrice) === toScaledPrice(group.lowest.unitPrice) && String(row.date).localeCompare(String(group.lowest.date)) > 0))) {
        group.lowest = row;
      }
      grouped.set(key, group);
    });
    return [...grouped.values()].filter((group) => group.lowest)
      .sort((a, b) => sort === '최저 단가순'
        ? toScaledPrice(a.lowest.unitPrice) < toScaledPrice(b.lowest.unitPrice) ? -1 : toScaledPrice(a.lowest.unitPrice) > toScaledPrice(b.lowest.unitPrice) ? 1 : a.itemName.localeCompare(b.itemName, 'ko')
        : sort === '최고 단가순'
          ? toScaledPrice(a.lowest.unitPrice) > toScaledPrice(b.lowest.unitPrice) ? -1 : toScaledPrice(a.lowest.unitPrice) < toScaledPrice(b.lowest.unitPrice) ? 1 : a.itemName.localeCompare(b.itemName, 'ko')
          : String(b.latestDate).localeCompare(String(a.latestDate)) || a.itemName.localeCompare(b.itemName, 'ko'));
  }, [filteredRows, sort]);
  const selectedSummary = summaryRows.find((row) => row.key === selectedKey) || null;
  const selected = selectedSummary?.lowest || null;
  const comparableRows = useMemo(() => exactPriceRows(filteredRows, selected).sort((a, b) => String(a.date).localeCompare(String(b.date))), [filteredRows, selected]);
  const pageCount = Math.max(1, Math.ceil(summaryRows.length / PAGE_SIZE));
  const pageRows = summaryRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const selectedRows = summaryRows.filter((row) => checkedKeys.includes(row.key)).map((row) => row.lowest);
  const selectedQuoteIds = [...new Set(selectedRows.map((row) => row.quoteId).filter(Boolean))].slice(0, 10);

  useEffect(() => {
    if (selectedQuoteIds.length < 2 || isDemo) { setCompareResult(null); setCompareError(''); return undefined; }
    const controller = new AbortController();
    setCompareError('');
    apiJson('/compare', { method: 'POST', signal: controller.signal, body: JSON.stringify({ quote_ids: selectedQuoteIds, item_name: selected?.itemName || submittedKeyword }) })
      .then(setCompareResult)
      .catch((reason) => { if (reason.name !== 'AbortError') { setCompareResult(null); setCompareError(reason.message || '비교 결과를 가져오지 못했습니다.'); } });
    return () => controller.abort();
  }, [selectedQuoteIds.join('|'), selected?.itemName, submittedKeyword, isDemo]);

  const availablePrices = comparableRows.map((row) => row.unitPrice).filter((price) => price !== null);
  const average = averagePrice(availablePrices);
  const minimum = comparableRows.reduce((best, row) => best === null || toScaledPrice(row.unitPrice) < toScaledPrice(best) ? row.unitPrice : best, null);
  const maximum = comparableRows.reduce((best, row) => best === null || toScaledPrice(row.unitPrice) > toScaledPrice(best) ? row.unitPrice : best, null);
  const summaryCurrency = selected?.currency || '';
  const offset = page * PAGE_SIZE;

  const submitSearch = (event) => { event.preventDefault(); setPage(0); setSelectedKey(''); setCheckedKeys([]); setSubmittedKeyword(keyword.trim()); };
  const selectRow = (row) => setSelectedKey((current) => current === row.key ? '' : row.key);
  const toggleChecked = (row) => setCheckedKeys((current) => current.includes(row.key) ? current.filter((key) => key !== row.key) : [...current, row.key]);
  const applyPriceToDraft = async () => {
    if (!selected?.quoteId || isDemo) { onNotify?.('실제 백엔드 이력에서 품목을 선택한 뒤 적용해 주세요.'); return; }
    if (selected.unitPrice === null) { onNotify?.('선택한 이력에는 단가가 없어 새 견적에 적용할 수 없습니다.'); return; }
    setApplyingPrice(true);
    try {
      const source = await apiJson(`/quotes/${encodeURIComponent(selected.quoteId)}`);
      const matchingItem = source.items?.find((item) => item.item_id === selected.itemId)
        || source.items?.find((item) => item.line_number === selected.lineNumber);
      if (!matchingItem) throw new Error('원본 견적에서 선택한 품목을 찾지 못했습니다.');
      const items = source.items.map((item) => ({
        item_name: item.item_name,
        original_item_name: item.original_item_name ?? null,
        specification: item.specification ?? null,
        unit: item.unit ?? null,
        quantity: item.quantity ?? null,
        unit_price: item.item_id === matchingItem.item_id || item.line_number === matchingItem.line_number ? selected.unitPrice : item.unit_price ?? null,
        amount: item.amount ?? null,
        currency: item.currency ?? null,
        raw_fields: item.raw_fields || {},
      }));
      const draft = await apiJson(`/quotes/${encodeURIComponent(selected.quoteId)}/drafts`, {
        method: 'POST', body: JSON.stringify({ overrides: { items } }),
      });
      onNotify?.(`선택한 단가를 적용한 새 견적 초안(${draft.quote_number || draft.quote_id})을 만들었습니다.`);
    } catch (reason) {
      onNotify?.(reason.message || '새 견적 초안을 만들지 못했습니다.');
    } finally {
      setApplyingPrice(false);
    }
  };
  const compareStatusText = compareResult?.comparison_status === 'comparable' ? '조건에 맞는 단가 비교' : compareResult?.comparison_status === 'conditional' ? '조건 차이가 있어 참고용으로 비교' : compareResult ? '비교 가능한 이력이 부족합니다' : '';

  return <section className="comparison-page">

    <form className="comparison-search-panel" onSubmit={submitSearch}>
      <label className="comparison-search-field"><b>품목 검색</b><span className="comparison-input"><Search /><input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="품목명으로 검색하세요." /></span></label>
      <label className="comparison-filter"><b>거래처</b><span className="select-wrap"><select value={customerFilter} onChange={(event) => { setCustomerFilter(event.target.value); setPage(0); }}><option>전체</option>{customers.map((customer) => <option key={customer}>{customer}</option>)}</select><ChevronDown /></span></label>
      <label className="comparison-filter"><b>기간</b><span className="select-wrap has-leading"><CalendarDays /><select value={periodFilter} onChange={(event) => { setPeriodFilter(event.target.value); setPage(0); }}><option>전체 기간</option><option value="3">최근 3개월</option><option value="6">최근 6개월</option><option value="12">최근 1년</option><option value="36">최근 3년</option></select><ChevronDown /></span></label>
      <label className="comparison-filter"><b>단위</b><span className="select-wrap"><select value={unitFilter} onChange={(event) => { setUnitFilter(event.target.value); setPage(0); }}><option>전체</option>{units.map((unit) => <option key={unit}>{unit}</option>)}</select><ChevronDown /></span></label>
      <label className="comparison-filter"><b>통화</b><span className="select-wrap"><select value={currencyFilter} onChange={(event) => { setCurrencyFilter(event.target.value); setPage(0); }}><option>전체</option>{currencies.map((currency) => <option key={currency}>{currency}</option>)}</select><ChevronDown /></span></label>
      <button className="primary-button comparison-submit" type="submit"><Search />검색</button>
    </form>

    {error && <div className="comparison-api-notice" role="status"><span>{isDemo ? '백엔드에 연결하지 못해 화면 예시 데이터를 표시 중입니다.' : error}</span><button type="button" onClick={() => setRetry((value) => value + 1)}>다시 연결</button></div>}

    <div className={`comparison-content-grid ${selected ? 'has-selection' : ''}`}>
      <section className="history-panel">
        <div className="history-panel-heading"><h2>검색 결과 <strong>{loading ? '…' : `${summaryRows.length}개 품목`}</strong></h2><div className="history-table-actions"><label className="sort-control"><span>정렬</span><span className="select-wrap"><select value={sort} onChange={(event) => { setSort(event.target.value); setPage(0); }}><option>최신순</option><option>최저 단가순</option><option>최고 단가순</option></select><ChevronDown /></span></label><button className="secondary-button export-button" type="button" onClick={() => downloadHistory(filteredRows)} disabled={!filteredRows.length}><Download />CSV 다운로드</button></div></div>
        {apiTotal > sourceRows.length && !isDemo && <div className="history-limit-note">검색 결과가 많아 최근 100건만 불러왔습니다. 검색어를 더 구체적으로 입력해 주세요.</div>}
        <div className="table-scroll"><table className="price-history-table"><thead><tr><th className="check-col"><input type="checkbox" aria-label="현재 페이지 전체 선택" checked={pageRows.length > 0 && pageRows.every((row) => checkedKeys.includes(row.key))} onChange={(event) => setCheckedKeys((current) => event.target.checked ? [...new Set([...current, ...pageRows.map((row) => row.key)])] : current.filter((key) => !pageRows.some((row) => row.key === key)))} /></th><th>품목명</th><th>최저 단가</th><th>거래처</th></tr></thead><tbody>
          {pageRows.map((row) => <tr key={row.key} className={selectedSummary?.key === row.key ? 'selected' : ''} onClick={() => selectRow(row)}><td className="check-col" onClick={(event) => event.stopPropagation()}><input type="checkbox" aria-label={`${row.itemName} 비교 선택`} checked={checkedKeys.includes(row.key)} onChange={() => toggleChecked(row)} /></td><td>{row.itemName}</td><td className="price-number">{formatPrice(row.lowest.unitPrice, row.lowest.currency)}</td><td>{row.lowest.customer}</td></tr>)}
        </tbody></table>{loading && <div className="comparison-loading"><LoaderCircle className="spin" />단가 이력을 불러오고 있습니다.</div>}{!loading && pageRows.length === 0 && <div className="comparison-loading">{error ? '예시 데이터를 표시 중입니다.' : '검색 결과가 없습니다. 품목명으로 검색해 주세요.'}</div>}</div>
        <div className="history-pagination"><label>페이지당 <select value={PAGE_SIZE} disabled><option value={PAGE_SIZE}>{PAGE_SIZE}개</option></select></label><div className="pagination-buttons"><button type="button" aria-label="이전 페이지" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}><ChevronLeft /></button><span>{page + 1} / {pageCount}</span><button type="button" aria-label="다음 페이지" disabled={page + 1 >= pageCount} onClick={() => setPage((value) => value + 1)}><ChevronRight /></button></div><small>총 {summaryRows.length}개 품목{!isDemo && apiTotal > sourceRows.length ? ` · 최근 ${sourceRows.length}건 범위` : ''}</small></div>
      </section>

      {selected && <aside className="comparison-side-column">
        <section className="selected-item-panel">
          {selected ? <>
            <div className="selected-item-heading"><div><span>{selected.itemName}</span><b>{formatDetails(selected.specification).map((line, index) => <React.Fragment key={`${index}-${line}`}>{index > 0 && <br />}{line}</React.Fragment>)}</b></div></div>
            <button className="apply-price-button" type="button" disabled={applyingPrice} onClick={applyPriceToDraft}>{applyingPrice ? <LoaderCircle className="spin" /> : <Plus />}{applyingPrice ? '초안 생성 중' : '새 견적에 적용'}</button>
            <div className="price-stats-grid"><StatCard label="평균 단가" value={average} currency={summaryCurrency} /><StatCard label="최저 단가" value={minimum} currency={summaryCurrency} /><StatCard label="최고 단가" value={maximum} currency={summaryCurrency} /></div>
            <div className="trend-heading"><h3>단가 추이</h3><div className="trend-controls"><span className="trend-currency">{summaryCurrency || '통화 미기재'}</span><span className="select-wrap"><select aria-label="단가 추이 기간" value={periodFilter} onChange={(event) => { setPeriodFilter(event.target.value); setPage(0); }}><option>전체 기간</option><option value="3">최근 3개월</option><option value="6">최근 6개월</option><option value="12">최근 1년</option><option value="36">최근 3년</option></select><ChevronDown /></span></div></div>
            <PriceTrend rows={comparableRows} />
          </> : <div className="selected-empty">품목을 검색하면 단가 요약과 추이를 볼 수 있습니다.</div>}
        </section>

        <section className="recent-history-panel"><div className="recent-history-heading"><h2>최근 견적 이력</h2><span>{selected.itemName}</span></div>
          {selected && <div className="recent-history-table-wrap"><table className="recent-history-table"><thead><tr><th>견적번호</th><th>작성일</th><th>거래처</th><th>수량</th><th>단가</th><th>상태</th></tr></thead><tbody>{[...comparableRows].sort((a, b) => String(b.date).localeCompare(String(a.date))).slice(0, 5).map((row) => <tr key={row.itemId}><td>{row.quoteId && !isDemo ? <button type="button" className="history-quote-link" onClick={() => onOpenQuote?.(row.quoteId, row.quoteNumber)}>{row.quoteNumber}</button> : row.quoteNumber || '—'}</td><td>{formatDate(row.date)}</td><td>{row.customer}</td><td>{row.quantity || '—'}</td><td>{formatPrice(row.unitPrice, row.currency)}</td><td><span className={`mini-status ${row.status === 'confirmed' ? 'done' : ''}`}>{statusLabels[row.status] || (isDemo ? '완료' : '—')}</span></td></tr>)}</tbody></table></div>}
          {selectedRows.length > 0 && <div className="compare-feedback">{selectedQuoteIds.length < 2 ? '비교하려면 서로 다른 견적 이력 2건 이상을 선택하세요.' : compareError ? compareError : compareResult ? <><b>{compareStatusText}</b><span>{compareResult.pairs?.length || 0}개 조합 · {compareResult.excluded_rows?.length || 0}개 비교 제외</span></> : '선택한 견적의 비교 조건을 확인하고 있습니다.'}</div>}
          {isDemo && <p className="demo-caption"><FileSpreadsheet />시안 예시 데이터 · 실제 견적 정보가 아닙니다.</p>}
        </section>
      </aside>}
    </div>
  </section>;
}
