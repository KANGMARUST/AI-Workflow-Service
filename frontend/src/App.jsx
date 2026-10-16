import React, { useState } from 'react';
import { BarChart3, Box, Check, ChevronDown, FileText, Home, Plus, UploadCloud, UserRound, X } from 'lucide-react';
import PriceComparison from './PriceComparison.jsx';
import Customers from './Customers.jsx';
import Items from './Items.jsx';
import HomePage from './HomePage.jsx';
import QuoteListPage from './QuoteListPage.jsx';

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
  const [file, setFile] = useState('');
  const [toast, setToast] = useState('');
  const [activeNav, setActiveNav] = useState('홈');
  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600); };

  const navigate = (label) => {
    setActiveNav(label);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (['홈', '견적서 목록', '단가 비교', '거래처 관리', '품목 관리'].includes(label)) return;
    notify(`${label} 화면은 준비 중입니다.`);
  };
  const addQuote = () => {
    if (!file) { notify('먼저 견적서 파일을 선택해 주세요.'); return; }
    const quote = { id: `Q-2026-${String(149 + quotes.length - seed.length).padStart(5, '0')}`, client: '거래처 확인 필요', date: '2026. 10. 15', amount: 0, status: '검토 미완료', title: file.replace(/\.[^.]+$/, '') };
    setQuotes((current) => [quote, ...current]); setUpload(false); setFile(''); notify('견적서가 목록에 추가되었습니다.');
  };

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top" onClick={() => navigate('홈')} aria-label="QuoteFlow 홈"><span className="brand-mark"><FileText /></span><span>QuoteFlow</span></a>
      <nav className="main-nav" aria-label="주 메뉴">{navItems.map(({ label, icon: Icon }) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => navigate(label)}><Icon />{label}</button>)}</nav>
      <button className="user-menu" onClick={() => notify('김담당님 계정 설정은 준비 중입니다.')}><span className="avatar">김</span><span>김담당님</span><ChevronDown /></button>
    </header>

    <main id="top" className="page-content">
      {activeNav === '단가 비교' ? <PriceComparison onNotify={notify} /> : activeNav === '거래처 관리' ? <Customers onNotify={notify} /> : activeNav === '품목 관리' ? <Items onNotify={notify} /> : activeNav === '견적서 목록' ? <QuoteListPage onUpload={() => setUpload(true)} onNotify={notify} /> : <HomePage quotes={quotes} onNotify={notify} onNavigate={navigate} onUpload={() => setUpload(true)} />}
    </main>

    {upload && <div className="modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget) setUpload(false); }}><section className="upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title"><div className="modal-heading"><div><span>NEW QUOTATION</span><h2 id="upload-title">견적서 등록</h2><p>등록할 견적서 원본 파일을 선택하세요.</p></div><button className="close-button" onClick={() => setUpload(false)} aria-label="닫기"><X /></button></div><label className="upload-drop"><UploadCloud /><b>{file || '파일을 선택하거나 여기에 놓으세요'}</b><small>PDF, Excel, 이미지 파일</small><input type="file" accept=".pdf,.xlsx,.xls,.png,.jpg,.jpeg" onChange={(event) => setFile(event.target.files?.[0]?.name || '')} /></label><p className="modal-note">업로드와 자동 추출은 API 연동 후 사용할 수 있습니다.</p><div className="modal-actions"><button className="secondary-button" onClick={() => setUpload(false)}>취소</button><button className="primary-button" onClick={addQuote}><Plus />등록</button></div></section></div>}
    {toast && <div className="toast"><Check />{toast}</div>}
  </div>;
}
