import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, FileText, Filter, LoaderCircle, MoreVertical, Plus, Search, Trash2 } from 'lucide-react';
import './QuoteListPage.css';
import QuoteReviewDialog from './QuoteReviewDialog.jsx';
import { requestQuote } from './quoteApi.js';

const PAGE_SIZE = 20;
const statusToApi = { '검토 미완료': 'review_required', '검토 완료': 'confirmed', '추출 중': 'extracting', 반려: 'rejected', 보관: 'archived' };
const statusFromApi = { review_required: '검토 미완료', extracting: '추출 중', confirmed: '검토 완료', rejected: '반려', archived: '보관' };
const amount = (value, currency) => {
  if (value == null || value === '') return '금액 미기재';
  const [integer, fraction] = String(value).split('.');
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return currency === 'KRW' ? `${grouped}${fraction ? `.${fraction}` : ''}원` : `${grouped}${fraction ? `.${fraction}` : ''}${currency ? ` ${currency}` : ''}`;
};

async function fetchQuotes({ keyword = '', status = '전체', direction, offset, signal }) {
  return requestQuote('/search', { method: 'POST', signal, body: JSON.stringify({ keyword: keyword.trim() || undefined, status: status === '전체' ? undefined : statusToApi[status], direction: direction || undefined, limit: PAGE_SIZE, offset }) });
}

function normalizeQuote(quote) {
  return { id: quote.quote_number || quote.quote_id, quoteId: quote.quote_id, title: quote.title || quote.source_filename || '', client: quote.customer_name || '거래처 미기재', date: quote.issue_date ? quote.issue_date.slice(0, 10).replaceAll('-', '. ') : '날짜 미기재', amount: amount(quote.total_amount, quote.currency), status: statusFromApi[quote.status] || quote.status || '상태 미기재', direction: quote.direction === 'sent' ? '보낸 견적서' : quote.direction === 'received' ? '받은 견적서' : '미분류', itemCount: quote.item_count ?? 0 };
}

export default function QuoteListPage({ onUpload, onNotify, initialQuote, onInitialQuoteHandled }) {
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState('전체');
  const [direction, setDirection] = useState('');
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [checked, setChecked] = useState([]);
  const [deleting, setDeleting] = useState(false);
  const [reviewId, setReviewId] = useState(null);
  const initialQuoteHandled = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    fetchQuotes({ keyword, status, direction, offset: page * PAGE_SIZE, signal: controller.signal })
      .then((payload) => {
        if (controller.signal.aborted) return;
        const total = payload.total || 0;
        setData({ items: (payload.items || []).map(normalizeQuote), total });
        if (page > 0 && page * PAGE_SIZE >= total) setPage(Math.max(0, Math.ceil(total / PAGE_SIZE) - 1));
      })
      .catch((reason) => { if (reason.name !== 'AbortError') { setData({ items: [], total: 0 }); setError(reason.message || '견적서 목록을 불러오지 못했습니다.'); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [keyword, status, direction, page, retry]);

  useEffect(() => {
    if (!initialQuote || initialQuoteHandled.current) return;
    initialQuoteHandled.current = true;
    const open = async () => {
      const knownId = initialQuote.backendQuoteId || initialQuote.quoteId;
      if (knownId) { setReviewId(knownId); return; }
      try {
        const result = await fetchQuotes({ keyword: initialQuote.id, status: '전체', offset: 0 });
        const found = (result.items || []).map(normalizeQuote).find((quote) => quote.id === initialQuote.id || quote.quoteId === initialQuote.id);
        if (found?.quoteId) setReviewId(found.quoteId);
        else onNotify?.(`견적서 ${initialQuote.id}를 백엔드 목록에서 찾지 못했습니다.`);
      } catch (reason) {
        onNotify?.(reason.message || '견적서 상세 정보를 찾지 못했습니다.');
      }
    };
    open();
    onInitialQuoteHandled?.();
  }, [initialQuote, onInitialQuoteHandled, onNotify]);

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const allChecked = data.items.length > 0 && data.items.every((item) => checked.includes(item.quoteId));
  const deleteSelected = async () => {
    if (!checked.length || deleting) return;
    const selectedIds = [...new Set(checked)];
    if (!window.confirm(`선택한 견적서 ${selectedIds.length}건을 휴지통으로 이동할까요? 휴지통에서 복원할 수 있습니다.`)) return;
    setDeleting(true);
    const results = await Promise.allSettled(selectedIds.map((id) => requestQuote(`/quotes/${encodeURIComponent(id)}`, { method: 'DELETE' })));
    const deletedIds = selectedIds.filter((_, index) => results[index].status === 'fulfilled');
    const failedCount = results.length - deletedIds.length;
    if (deletedIds.length) {
      setChecked((current) => current.filter((id) => !deletedIds.includes(id)));
      setRetry((value) => value + 1);
    }
    setDeleting(false);
    if (failedCount) onNotify?.(`${deletedIds.length}건을 휴지통으로 옮겼고, ${failedCount}건은 처리하지 못했습니다.`);
    else onNotify?.(`${deletedIds.length}건을 휴지통으로 옮겼습니다.`);
  };

  return <section className="all-quotes-page">
    <section className="all-quotes-panel"><div className="all-quotes-toolbar"><div className="list-count"><b>전체 견적서</b><span>{loading ? '불러오는 중…' : `${data.total.toLocaleString('ko-KR')}건`}</span></div><div className="list-filters"><label className="search-box list-search"><Search /><input value={keyword} onChange={(event) => { setKeyword(event.target.value); setPage(0); }} placeholder="견적번호, 거래처, 품목 검색" aria-label="견적서 검색" /></label><label className="status-filter"><Filter /><select aria-label="검토 상태 필터" value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}><option value="전체">전체 상태</option><option>검토 미완료</option><option>추출 중</option><option>검토 완료</option><option>반려</option><option>보관</option></select><ChevronDown /></label><label className="status-filter direction-filter"><select aria-label="견적서 구분 필터" value={direction} onChange={(event) => { setDirection(event.target.value); setPage(0); }}><option value="">전체 구분</option><option value="received">받은 견적서</option><option value="sent">보낸 견적서</option></select><ChevronDown /></label>{checked.length > 0 && <button className="delete-selected-button" type="button" onClick={deleteSelected} disabled={deleting || loading}><Trash2 />{deleting ? '이동 중…' : `삭제 ${checked.length}건`}</button>}<button className="primary-button register-button list-register-button" onClick={onUpload}><Plus />견적서 등록</button></div></div>
      {error && <div className="api-error" role="alert"><b>연결을 확인해 주세요.</b><span>{error}</span><button onClick={() => setRetry((value) => value + 1)}>다시 시도</button></div>}
      <div className="table-scroll"><table className="quotes-table all-quotes-table"><thead><tr><th className="check-col"><input aria-label="현재 페이지 전체 선택" type="checkbox" checked={allChecked} onChange={(event) => setChecked((current) => event.target.checked ? [...new Set([...current, ...data.items.map((item) => item.quoteId)])] : current.filter((id) => !data.items.some((item) => item.quoteId === id)))} /></th><th>견적번호</th><th>거래처</th><th>구분</th><th>작성일</th><th>견적 금액</th><th>진행 상태</th><th aria-label="메뉴" /></tr></thead><tbody>{data.items.map((quote) => <tr key={quote.quoteId} className="quote-review-row" onClick={() => setReviewId(quote.quoteId)}><td className="check-col" onClick={(event) => event.stopPropagation()}><input aria-label={`${quote.id} 선택`} type="checkbox" checked={checked.includes(quote.quoteId)} onChange={(event) => setChecked((current) => event.target.checked ? [...new Set([...current, quote.quoteId])] : current.filter((id) => id !== quote.quoteId))} /></td><td className="quote-id"><button className="quote-review-link" aria-label={`${quote.id} 견적서 검토`} onClick={(event) => { event.stopPropagation(); setReviewId(quote.quoteId); }}>{quote.id}</button>{quote.title && <small className="quote-subtitle">{quote.title}</small>}</td><td className="client-name">{quote.client}<small className="quote-subtitle">{quote.itemCount}개 품목</small></td><td><span className={`direction-pill ${quote.direction === '받은 견적서' ? 'received' : quote.direction === '보낸 견적서' ? 'sent' : ''}`}>{quote.direction}</span></td><td>{quote.date}</td><td className="amount-cell">{quote.amount}</td><td><span className={`status-pill ${quote.status === '검토 완료' ? 'complete' : quote.status === '추출 중' ? 'in-progress' : quote.status === '반려' ? 'rejected' : 'pending'}`}>{quote.status}</span></td><td><button className="row-menu" aria-label={`${quote.id} 상세 보기`} onClick={(event) => { event.stopPropagation(); setReviewId(quote.quoteId); }}><MoreVertical /></button></td></tr>)}</tbody></table>
        {loading && <div className="list-state"><LoaderCircle className="spin" />견적서 목록을 불러오고 있습니다.</div>}
        {!loading && !error && data.items.length === 0 && <div className="list-state"><FileText />{keyword || status !== '전체' || direction ? '검색 조건에 맞는 견적서가 없습니다.' : '등록된 견적서가 없습니다.'}</div>}
      </div>
      <div className="pagination"><span>{data.total ? `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, data.total)} / ${data.total.toLocaleString('ko-KR')}` : '0건'}</span><div><button aria-label="이전 페이지" disabled={page === 0 || loading} onClick={() => setPage((value) => Math.max(0, value - 1))}><ChevronLeft /></button><span className="page-indicator">{page + 1} / {totalPages}</span><button aria-label="다음 페이지" disabled={page + 1 >= totalPages || loading} onClick={() => setPage((value) => value + 1)}><ChevronRight /></button></div></div>
    </section>
    {reviewId && <QuoteReviewDialog key={reviewId} quoteId={reviewId} onClose={() => setReviewId(null)} onSaved={() => setRetry((value) => value + 1)} onNotify={onNotify} />}
  </section>;
}
