import React, { useState } from 'react';
import { Bell, Check, ChevronRight, Globe2, LockKeyhole, Save, UserRound } from 'lucide-react';
import './SettingsPage.css';

const STORAGE_KEY = 'quoteflow-settings-v1';
const defaults = {
  name: '김담당', email: '', department: '구매팀', role: '관리자',
  language: 'ko', timezone: 'Asia/Seoul', dateFormat: 'YYYY. MM. DD',
  emailNotifications: true, reviewNotifications: true,
};

function loadSettings() {
  try { return { ...defaults, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') }; }
  catch { return defaults; }
}

export default function SettingsPage({ onNotify }) {
  const [settings, setSettings] = useState(loadSettings);
  const [section, setSection] = useState('account');
  const update = (key, value) => setSettings((current) => ({ ...current, [key]: value }));
  const save = (event) => {
    event.preventDefault();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    onNotify?.('설정을 저장했습니다.');
  };

  return <div className="settings-page">
    <header className="settings-page-heading"><div><span>SETTINGS</span><h1>계정 설정</h1><p>계정 정보와 QuoteFlow 사용 환경을 관리하세요.</p></div><button className="primary-button settings-save" onClick={save}><Save />변경 사항 저장</button></header>
    <div className="settings-layout">
      <nav className="settings-nav" aria-label="설정 메뉴">
        <button className={section === 'account' ? 'active' : ''} onClick={() => setSection('account')}><UserRound />계정 설정<ChevronRight /></button>
        <button className={section === 'general' ? 'active' : ''} onClick={() => setSection('general')}><Globe2 />일반 설정<ChevronRight /></button>
        <div className="settings-nav-note"><LockKeyhole /><span>계정 정보와 개인 환경 설정은 이 브라우저에 저장됩니다.</span></div>
      </nav>

      <form className="settings-form" onSubmit={save}>
        {section === 'account' ? <>
          <section className="settings-card account-card"><header><div><h2>계정 정보</h2><p>QuoteFlow에서 사용할 프로필 정보를 확인하고 수정할 수 있습니다.</p></div></header>
            <div className="settings-profile"><div className="settings-avatar">{settings.name.trim().slice(0, 1) || '김'}</div><div><b>{settings.name || '사용자'}</b><small>{settings.role} · {settings.department}</small></div></div>
            <div className="settings-fields">
              <label>이름<input value={settings.name} onChange={(event) => update('name', event.target.value)} placeholder="이름" /></label>
              <label>이메일<input type="email" value={settings.email} onChange={(event) => update('email', event.target.value)} placeholder="이메일 주소를 입력하세요" /></label>
              <label>부서<input value={settings.department} onChange={(event) => update('department', event.target.value)} placeholder="부서" /></label>
              <label>권한<input value={settings.role} readOnly /></label>
            </div>
          </section>
          <section className="settings-card"><header><div><h2>보안</h2><p>계정 보안을 위한 인증 설정을 관리합니다.</p></div></header><div className="settings-info-row"><span><b>비밀번호</b><small>비밀번호 변경 기능은 계정 인증 서비스 연결 후 사용할 수 있습니다.</small></span><button type="button" className="secondary-button" disabled>변경</button></div></section>
        </> : <>
          <section className="settings-card"><header><div><h2>일반 설정</h2><p>언어와 날짜 표시 등 서비스 사용 환경을 설정합니다.</p></div></header>
            <div className="settings-fields settings-fields-general">
              <label>표시 언어<select value={settings.language} onChange={(event) => update('language', event.target.value)}><option value="ko">한국어</option><option value="en">English</option></select></label>
              <label>시간대<select value={settings.timezone} onChange={(event) => update('timezone', event.target.value)}><option value="Asia/Seoul">서울 (GMT+9)</option><option value="UTC">UTC (GMT+0)</option><option value="America/Los_Angeles">로스앤젤레스</option></select></label>
              <label>날짜 형식<select value={settings.dateFormat} onChange={(event) => update('dateFormat', event.target.value)}><option>YYYY. MM. DD</option><option>YYYY-MM-DD</option><option>MM/DD/YYYY</option></select></label>
            </div>
          </section>
          <section className="settings-card"><header><div><h2>알림</h2><p>견적서 검토와 주요 변경 알림을 설정합니다.</p></div></header>
            <label className="settings-toggle-row"><span className="settings-toggle-icon"><Bell /></span><span className="settings-toggle-copy"><b>이메일 알림</b><small>견적서 등록 및 처리 결과를 이메일로 받기</small></span><input type="checkbox" checked={settings.emailNotifications} onChange={(event) => update('emailNotifications', event.target.checked)} /></label>
            <label className="settings-toggle-row"><span className="settings-toggle-icon"><Check /></span><span className="settings-toggle-copy"><b>검토 알림</b><small>검토할 견적서와 검토 완료 상태 알림 받기</small></span><input type="checkbox" checked={settings.reviewNotifications} onChange={(event) => update('reviewNotifications', event.target.checked)} /></label>
          </section>
        </>}
        <div className="settings-mobile-save"><button className="primary-button" type="submit"><Save />변경 사항 저장</button></div>
      </form>
    </div>
  </div>;
}
