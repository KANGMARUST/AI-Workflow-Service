import React, { useEffect, useState } from 'react';
import { AlertCircle, BarChart3, Box, Check, ChevronDown, FileText, Home, LoaderCircle, MessageCircle, Plus, UploadCloud, UserRound, X } from 'lucide-react';
import PriceComparison from './PriceComparison.jsx';
import Customers from './Customers.jsx';
import Items from './Items.jsx';
import HomePage from './HomePage.jsx';
import QuoteListPage from './QuoteListPage.jsx';
import { requestQuote } from './quoteApi.js';
import SettingsPage from './SettingsPage.jsx';
import QuoteChatPage from './QuoteChatPage.jsx';

const apiPrefixRaw = (import.meta.env.VITE_API_PREFIX || '/api').replace(/\/$/, '');
const API_PREFIX = apiPrefixRaw.startsWith('/') ? apiPrefixRaw : `/${apiPrefixRaw}`;
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';

async function requestApi(path, options = {}) {
  const headers = { ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}), ...(options.headers || {}) };
  const response = await fetch(`${API_BASE}${API_PREFIX}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join(', ') : '요청을 처리하지 못했습니다.';
    throw new Error(`${response.status}: ${detail}`);
  }
  return payload;
}

const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

const quoteStatus = { review_required: '검토 미완료', extracting: '추출 중', confirmed: '검토 완료', rejected: '반려', archived: '보관' };
const homeQuote = (quote) => ({
  id: quote.quote_number || quote.quote_id,
  quoteId: quote.quote_id,
  backendQuoteId: quote.quote_id,
  client: quote.customer_name || '거래처 미기재',
  date: quote.issue_date ? quote.issue_date.slice(0, 10).replaceAll('-', '. ') : '날짜 미기재',
  amount: quote.total_amount == null ? 0 : Number(quote.total_amount),
  status: quoteStatus[quote.status] || quote.status || '상태 미기재',
  title: quote.title || quote.source_filename || '',
});

const navItems = [
  { label: '홈', icon: Home }, { label: '견적서 목록', icon: FileText },
  { label: '단가 비교', icon: BarChart3 }, { label: '거래처 관리', icon: UserRound },
  { label: '품목 관리', icon: Box }, { label: '견적서 AI', icon: MessageCircle },
];

export default function App() {
  const [quotes, setQuotes] = useState([]);
  const [quotesLoading, setQuotesLoading] = useState(true);
  const [quotesError, setQuotesError] = useState('');
  const [upload, setUpload] = useState(false);
  const [uploadDirection, setUploadDirection] = useState('received');
  const [uploadFiles, setUploadFiles] = useState([]);
  const [uploadState, setUploadState] = useState('idle');
  const [uploadMessage, setUploadMessage] = useState('');
  const [quoteListRefresh, setQuoteListRefresh] = useState(0);
  const [pendingQuote, setPendingQuote] = useState(null);
  const [toast, setToast] = useState('');
  const [activeNav, setActiveNav] = useState('홈');
  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600); };

  useEffect(() => {
    const controller = new AbortController();
    setQuotesLoading(true);
    setQuotesError('');
    requestQuote('/search', { method: 'POST', signal: controller.signal, body: JSON.stringify({ limit: 5, offset: 0 }) })
      .then((payload) => {
        if (!controller.signal.aborted) setQuotes((payload.items || []).map(homeQuote));
      })
      .catch((reason) => {
        if (reason.name !== 'AbortError') {
          setQuotes([]);
          setQuotesError(reason.message || '최근 견적서를 불러오지 못했습니다.');
        }
      })
      .finally(() => { if (!controller.signal.aborted) setQuotesLoading(false); });
    return () => controller.abort();
  }, [quoteListRefresh]);

  const navigate = (label) => {
    setPendingQuote(null);
    if (activeNav !== label) setQuoteListRefresh((value) => value + 1);
    setActiveNav(label);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (['홈', '견적서 목록', '단가 비교', '거래처 관리', '품목 관리', '견적서 AI', '설정'].includes(label)) return;
    notify(`${label} 화면은 준비 중입니다.`);
  };
  const openQuoteFromHome = (quote) => {
    setPendingQuote(quote);
    setActiveNav('견적서 목록');
    setQuoteListRefresh((value) => value + 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const openQuoteRecord = (quoteId, displayId) => {
    setPendingQuote({ id: displayId || quoteId, quoteId, backendQuoteId: quoteId });
    setActiveNav('견적서 목록');
    setQuoteListRefresh((value) => value + 1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const updateUploadFile = (id, updates) => setUploadFiles((current) => current.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const selectUploadFiles = (fileList) => {
    const selected = Array.from(fileList || []).filter((candidate) => /\.(pdf|xlsx)$/i.test(candidate.name));
    if (!selected.length) {
      setUploadFiles([]); setUploadState('error'); setUploadMessage('PDF 또는 XLSX 파일을 선택해 주세요.'); return;
    }
    setUploadFiles(selected.map((candidate, index) => ({ id: `${Date.now()}-${index}-${candidate.name}`, file: candidate, status: 'queued', message: '대기 중' })));
    setUploadState('idle'); setUploadMessage('');
  };
  const processUploadFile = async (entry) => {
    let quoteId = '';
    try {
      updateUploadFile(entry.id, { status: 'uploading', message: '파일 업로드 중' });
      const form = new FormData();
      form.append('file', entry.file);
      form.append('direction', uploadDirection);
      const uploaded = await requestApi('/add', { method: 'POST', body: form });
      quoteId = uploaded.quote_id;
      if (!quoteId) throw new Error('업로드 응답에서 견적 ID를 받지 못했습니다.');

      let job = null;
      if (uploaded.duplicate && uploaded.extraction_status !== 'completed') {
        const extraction = await requestApi(`/extract?quote_id=${encodeURIComponent(quoteId)}`);
        job = extraction.latest_job;
      }
      if (!uploaded.duplicate || uploaded.extraction_status !== 'completed') {
        if (!job || !['queued', 'running', 'completed'].includes(job.status)) {
          updateUploadFile(entry.id, { status: 'extracting', message: 'Upstage 항목 추출 요청 중' });
          job = await requestApi('/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quote_id: quoteId, provider: 'upstage' }) });
        } else if (['queued', 'running'].includes(job.status)) {
          updateUploadFile(entry.id, { status: 'extracting', message: '추출 작업을 기다리는 중' });
        }
        if (job && ['queued', 'running'].includes(job.status)) {
          const startedAt = Date.now();
          while (['queued', 'running'].includes(job.status) && Date.now() - startedAt < 210000) {
            await wait(1500);
            job = await requestApi(`/jobs/${encodeURIComponent(job.job_id)}`);
            updateUploadFile(entry.id, { status: 'extracting', message: job.status === 'queued' ? '추출 대기 중' : '항목 추출 중' });
          }
        }
        if (job && job.status !== 'completed') throw new Error(job.error || '항목 추출이 제한 시간 안에 완료되지 않았습니다.');
      }
      const detail = await requestApi(`/quotes/${encodeURIComponent(quoteId)}`);
      updateUploadFile(entry.id, { status: 'completed', message: `완료 · 품목 ${detail.items?.length || 0}개${uploaded.duplicate ? ' (중복 문서)' : ''}` });
      return true;
    } catch (reason) {
      updateUploadFile(entry.id, { status: 'error', message: reason.message || (quoteId ? '추출을 완료하지 못했습니다.' : '파일을 등록하지 못했습니다.') });
      return false;
    }
  };
  const addQuote = async () => {
    if (!uploadFiles.length) { setUploadState('error'); setUploadMessage('먼저 PDF 또는 XLSX 파일을 선택해 주세요.'); return; }
    const pending = uploadFiles.filter((entry) => entry.status === 'queued' || entry.status === 'error');
    if (!pending.length) return;
    setUploadState('uploading'); setUploadMessage(`${pending.length}개 파일을 순서대로 처리하고 있습니다.`);
    let failures = 0;
    for (let index = 0; index < pending.length; index += 1) {
      const entry = pending[index];
      setUploadMessage(`${index + 1}/${pending.length} 처리 중 · ${entry.file.name}`);
      const completed = await processUploadFile(entry);
      if (!completed) failures += 1;
      setQuoteListRefresh((value) => value + 1);
    }
    setUploadState(failures ? 'error' : 'completed');
    setUploadMessage(failures ? `${pending.length}개 중 ${failures}개 처리 실패 · 실패 파일만 다시 시도할 수 있습니다.` : `${pending.length}개 파일 처리가 완료됐습니다.`);
  };

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top" onClick={() => navigate('홈')} aria-label="모두의 견적서 홈"><img className="brand-logo" src="/modu-quote-logo.png" alt="" aria-hidden="true" /><span>모두의 견적서</span></a>
      <nav className="main-nav" aria-label="주 메뉴">{navItems.map(({ label, icon: Icon }) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => navigate(label)}><Icon />{label}</button>)}</nav>
      <button className="user-menu" onClick={() => navigate('설정')} aria-label="계정 설정 열기"><span className="avatar">김</span><span>김담당님</span><ChevronDown /></button>
    </header>

    <main id="top" className="page-content">
      {activeNav === '설정' ? <SettingsPage onNotify={notify} /> : activeNav === '견적서 AI' ? <QuoteChatPage onNotify={notify} /> : activeNav === '단가 비교' ? <PriceComparison refreshKey={quoteListRefresh} onNotify={notify} onOpenQuote={openQuoteRecord} /> : activeNav === '거래처 관리' ? <Customers refreshKey={quoteListRefresh} onNotify={notify} onOpenQuote={openQuoteRecord} /> : activeNav === '품목 관리' ? <Items refreshKey={quoteListRefresh} onNotify={notify} onOpenQuote={openQuoteRecord} /> : activeNav === '견적서 목록' ? <QuoteListPage key={quoteListRefresh} initialQuote={pendingQuote} onInitialQuoteHandled={() => setPendingQuote(null)} onUpload={() => setUpload(true)} onNotify={notify} /> : <HomePage quotes={quotes} quotesLoading={quotesLoading} quotesError={quotesError} onNotify={notify} onNavigate={navigate} onOpenQuote={openQuoteFromHome} onUpload={() => setUpload(true)} />}
    </main>

    {upload && <div className="modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget && uploadState !== 'uploading') setUpload(false); }}><section className="upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title"><div className="modal-heading"><div><span>NEW QUOTATION</span><h2 id="upload-title">견적서 등록</h2><p>여러 PDF 또는 XLSX 파일을 선택하면 순서대로 업로드하고 항목을 추출합니다.</p></div><button className="close-button" onClick={() => setUpload(false)} aria-label="닫기" disabled={uploadState === 'uploading'}><X /></button></div><label className="upload-direction"><b>견적서 구분</b><select aria-label="견적서 구분" value={uploadDirection} disabled={uploadState === 'uploading'} onChange={(event) => setUploadDirection(event.target.value)}><option value="received">받은 견적서</option><option value="sent">보낸 견적서</option></select></label><label className="upload-drop"><UploadCloud /><b>{uploadFiles.length ? `${uploadFiles.length}개 파일 선택됨` : '파일을 선택하거나 여기에 놓으세요'}</b><small>PDF 또는 XLSX · 파일별 순차 처리 및 Upstage 항목 추출</small><input type="file" accept=".pdf,.xlsx" multiple disabled={uploadState === 'uploading'} onChange={(event) => { selectUploadFiles(event.target.files); event.target.value = ''; }} /></label>{uploadFiles.length > 0 && <ul className="upload-file-list" aria-label="선택한 파일 목록">{uploadFiles.map((entry) => <li key={entry.id} className={`upload-file ${entry.status}`}><FileText /><span className="upload-file-name" title={entry.file.name}>{entry.file.name}</span><small>{entry.status === 'uploading' || entry.status === 'extracting' ? <LoaderCircle className="spin" /> : entry.status === 'completed' ? <Check /> : entry.status === 'error' ? <AlertCircle /> : null}{entry.message}</small></li>)}</ul>}{uploadMessage && <p className={`upload-progress ${uploadState}`} role="status">{uploadMessage}</p>}<div className="modal-actions"><button className="secondary-button" onClick={() => setUpload(false)} disabled={uploadState === 'uploading'}>닫기</button><button className="primary-button" onClick={uploadState === 'completed' ? () => setUpload(false) : addQuote} disabled={uploadState === 'uploading' || !uploadFiles.length}>{uploadState === 'uploading' ? <LoaderCircle className="spin" /> : uploadState === 'completed' ? <Check /> : uploadState === 'error' ? <AlertCircle /> : <Plus />}{uploadState === 'uploading' ? '처리 중' : uploadState === 'completed' ? '완료' : uploadState === 'error' ? '실패 파일 다시 시도' : `${uploadFiles.length || ''}건 등록 시작`}</button></div></section></div>}
    {toast && <div className="toast"><Check />{toast}</div>}
  </div>;
}
