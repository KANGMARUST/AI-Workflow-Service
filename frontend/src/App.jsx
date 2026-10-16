import React, { useState } from 'react';
import { BarChart3, Box, Check, ChevronDown, FileText, Home, LoaderCircle, Plus, UploadCloud, UserRound, X } from 'lucide-react';
import PriceComparison from './PriceComparison.jsx';
import Customers from './Customers.jsx';
import Items from './Items.jsx';
import HomePage from './HomePage.jsx';
import QuoteListPage from './QuoteListPage.jsx';

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

const seed = [
  { id: 'Q-2026-00148', client: '㈜한빛테크', date: '2026. 10. 14', amount: 12500000, status: '검토 미완료', title: '산업용 센서 모듈 공급 견적' },
  { id: 'Q-2026-00147', client: '삼성전자㈜', date: '2026. 10. 13', amount: 5300000, status: '검토 완료', title: '자동화 설비 부품 견적서' },
  { id: 'Q-2026-00146', client: '㈜미래솔루션', date: '2026. 10. 11', amount: 8750000, status: '검토 완료', title: '컨트롤 패널 및 부속품' },
  { id: 'Q-2026-00145', client: 'LG디스플레이㈜', date: '2026. 10. 09', amount: 21000000, status: '검토 미완료', title: '디스플레이 부품 공급 견적' },
  { id: 'Q-2026-00144', client: '㈜현대엔지니어링', date: '2026. 10. 06', amount: 4200000, status: '검토 완료', title: '정밀 가공 부품 단가 제안' },
];

const navItems = [
  { label: '홈', icon: Home }, { label: '견적서 목록', icon: FileText },
  { label: '단가 비교', icon: BarChart3 }, { label: '거래처 관리', icon: UserRound },
  { label: '품목 관리', icon: Box },
  { label: '프로필', icon: UserRound },
];

export default function App() {
  const [quotes, setQuotes] = useState(seed);
  const [upload, setUpload] = useState(false);
  const [file, setFile] = useState(null);
  const [uploadState, setUploadState] = useState('idle');
  const [uploadMessage, setUploadMessage] = useState('');
  const [quoteListRefresh, setQuoteListRefresh] = useState(0);
  const [toast, setToast] = useState('');
  const [activeNav, setActiveNav] = useState('홈');
  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600); };

  const navigate = (label) => {
    setActiveNav(label);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (['홈', '견적서 목록', '단가 비교', '거래처 관리', '품목 관리'].includes(label)) return;
    notify(`${label} 화면은 준비 중입니다.`);
  };
  const addQuote = async () => {
    if (!file) { setUploadState('error'); setUploadMessage('먼저 PDF 또는 XLSX 파일을 선택해 주세요.'); return; }
    setUploadState('uploading'); setUploadMessage('파일을 백엔드에 업로드하고 있습니다.');
    let quoteId = '';
    try {
      const form = new FormData();
      form.append('file', file);
      const uploaded = await requestApi('/add', { method: 'POST', body: form });
      quoteId = uploaded.quote_id;
      if (!quoteId) throw new Error('업로드 응답에서 견적 ID를 받지 못했습니다.');
      setQuoteListRefresh((value) => value + 1);

      let job = null;
        if (uploaded.duplicate && uploaded.extraction_status === 'completed') {
          setUploadMessage('이미 등록된 문서입니다. 기존 추출 결과를 불러오고 있습니다.');
        } else {
        if (uploaded.duplicate) {
          const extraction = await requestApi(`/extract?quote_id=${encodeURIComponent(quoteId)}`);
          job = extraction.latest_job;
        }
        if (!job || !['queued', 'running', 'completed'].includes(job.status)) {
          setUploadState('extracting');
          setUploadMessage('파일 업로드 완료 · Upstage API에 항목 추출을 요청하고 있습니다.');
          job = await requestApi('/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quote_id: quoteId, provider: 'upstage' }) });
        } else if (['queued', 'running'].includes(job.status)) {
          setUploadState('extracting');
          setUploadMessage('이미 시작된 항목 추출 작업을 확인하고 있습니다.');
        }
        if (job && ['queued', 'running'].includes(job.status)) {
          const startedAt = Date.now();
          while (['queued', 'running'].includes(job.status) && Date.now() - startedAt < 210000) {
            await wait(1500);
            job = await requestApi(`/jobs/${encodeURIComponent(job.job_id)}`);
            setUploadMessage(job.status === 'queued' ? 'Upstage 추출 작업 대기 중…' : 'Upstage API에서 항목을 추출하고 있습니다…');
          }
        }
        if (job && job.status !== 'completed') throw new Error(job.error || '항목 추출이 제한 시간 안에 완료되지 않았습니다.');
      }

      const detail = await requestApi(`/quotes/${encodeURIComponent(quoteId)}`);
      const quote = {
        id: detail.quote_number || uploaded.quote_number || quoteId,
        backendQuoteId: quoteId,
        client: detail.customer_name || '거래처 미기재',
        date: detail.issue_date ? detail.issue_date.slice(0, 10).replaceAll('-', '. ') : '날짜 미기재',
        amount: detail.total_amount ? Number(detail.total_amount) : 0,
        status: detail.status === 'confirmed' ? '검토 완료' : '검토 미완료',
        title: detail.title || detail.source_filename || file.name,
      };
      setQuotes((current) => [quote, ...current.filter((item) => item.backendQuoteId !== quoteId)]);
      setQuoteListRefresh((value) => value + 1);
      setUploadState('completed');
      setUploadMessage(`Upstage 추출 완료 · 품목 ${detail.items?.length || 0}개를 견적서에 저장했습니다.`);
    } catch (reason) {
      if (quoteId) setQuoteListRefresh((value) => value + 1);
      setUploadState('error');
      setUploadMessage(quoteId ? `파일은 등록됐지만 추출을 완료하지 못했습니다. ${reason.message || '잠시 후 다시 시도해 주세요.'}` : reason.message || '파일을 등록하지 못했습니다.');
    }
  };

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top" onClick={() => navigate('홈')} aria-label="QuoteFlow 홈"><span className="brand-mark"><FileText /></span><span>QuoteFlow</span></a>
      <nav className="main-nav" aria-label="주 메뉴">{navItems.map(({ label, icon: Icon }) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => navigate(label)}><Icon />{label}</button>)}</nav>
      <button className="user-menu" onClick={() => notify('김담당님 계정 설정은 준비 중입니다.')}><span className="avatar">김</span><span>김담당님</span><ChevronDown /></button>
    </header>

    <main id="top" className="page-content">
      {activeNav === '단가 비교' ? <PriceComparison onNotify={notify} /> : activeNav === '거래처 관리' ? <Customers onNotify={notify} /> : activeNav === '품목 관리' ? <Items onNotify={notify} /> : activeNav === '견적서 목록' ? <QuoteListPage key={quoteListRefresh} onUpload={() => setUpload(true)} onNotify={notify} /> : <HomePage quotes={quotes} onNotify={notify} onNavigate={navigate} onUpload={() => setUpload(true)} />}
    </main>

    {upload && <div className="modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget) setUpload(false); }}><section className="upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title"><div className="modal-heading"><div><span>NEW QUOTATION</span><h2 id="upload-title">견적서 등록</h2><p>등록할 견적서 원본 파일을 선택하세요.</p></div><button className="close-button" onClick={() => setUpload(false)} aria-label="닫기"><X /></button></div><label className="upload-drop"><UploadCloud /><b>{file?.name || '파일을 선택하거나 여기에 놓으세요'}</b><small>PDF 또는 XLSX · 등록 후 Upstage 항목 추출</small><input type="file" accept=".pdf,.xlsx" onChange={(event) => { setFile(event.target.files?.[0] || null); setUploadState('idle'); setUploadMessage(''); }} /></label>{uploadMessage && <p className={`upload-progress ${uploadState}`} role="status">{uploadMessage}</p>}<div className="modal-actions"><button className="secondary-button" onClick={() => setUpload(false)}>닫기</button><button className="primary-button" onClick={uploadState === 'completed' ? () => setUpload(false) : addQuote} disabled={['uploading', 'extracting'].includes(uploadState)}>{['uploading', 'extracting'].includes(uploadState) ? <LoaderCircle className="spin" /> : uploadState === 'completed' ? <Check /> : <Plus />}{uploadState === 'uploading' ? '업로드 중' : uploadState === 'extracting' ? '추출 중' : uploadState === 'completed' ? '완료' : uploadState === 'error' ? '다시 시도' : '등록'}</button></div></section></div>}
    {toast && <div className="toast"><Check />{toast}</div>}
  </div>;
}
