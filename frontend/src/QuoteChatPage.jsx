import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, Check, ChevronDown, FileText, LoaderCircle, MessageCircle, Plus, Send, Trash2, UserRound, X } from 'lucide-react';
import { requestQuote } from './quoteApi.js';
import './QuoteChatPage.css';

const money = (value, currency) => {
  if (value == null || value === '') return '금액 미기재';
  const [integer, fraction] = String(value).split('.');
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${grouped}${fraction ? `.${fraction}` : ''}${currency === 'KRW' ? '원' : currency ? ` ${currency}` : ''}`;
};
const shortDate = (value) => value ? value.slice(0, 10).replaceAll('-', '.') : '날짜 미기재';
const displayQuote = (quote) => quote?.quote_number || quote?.title || quote?.source_filename || quote?.quote_id || '견적서';
const chatTitle = (chat, quoteMap) => chat.title && chat.title !== '견적서 대화' ? chat.title : (chat.quote_ids || []).map((id) => displayQuote(quoteMap.get(id))).join(', ') || '견적서 대화';

function Citation({ source, quoteMap }) {
  const quote = quoteMap.get(source.quote_id);
  return <li className="chat-citation"><b>{displayQuote(quote)}</b><span>{source.field_path}</span><p>{source.value == null ? '미기재' : String(source.value)}</p></li>;
}

export default function QuoteChatPage({ onNotify }) {
  const [chats, setChats] = useState([]);
  const [quotes, setQuotes] = useState([]);
  const [models, setModels] = useState([]);
  const [defaultModel, setDefaultModel] = useState('');
  const [activeChat, setActiveChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [selectedQuotes, setSelectedQuotes] = useState([]);
  const [quoteSearch, setQuoteSearch] = useState('');
  const [question, setQuestion] = useState('');
  const [chatModel, setChatModel] = useState('');
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingChat, setLoadingChat] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [deleting, setDeleting] = useState(false);
  const messageEnd = useRef(null);
  const questionBox = useRef(null);
  const quoteMap = useMemo(() => new Map(quotes.map((quote) => [quote.quote_id, quote])), [quotes]);
  const filteredQuotes = useMemo(() => {
    const query = quoteSearch.trim().toLocaleLowerCase();
    return quotes.filter((quote) => !query || [quote.quote_number, quote.title, quote.customer_name, quote.source_filename].some((value) => String(value || '').toLocaleLowerCase().includes(query)));
  }, [quotes, quoteSearch]);

  const refreshChats = async () => {
    const result = await requestQuote('/chats?limit=100&offset=0');
    setChats(result.items || []);
    return result.items || [];
  };

  const loadChat = async (chatId) => {
    setLoadingChat(true); setError(''); setCreating(false);
    try {
      const [detail, history] = await Promise.all([
        requestQuote(`/chats/${encodeURIComponent(chatId)}`),
        requestQuote(`/chats/${encodeURIComponent(chatId)}/messages?limit=100&offset=0`),
      ]);
      setActiveChat(detail);
      setChatModel(detail.model || defaultModel);
      setMessages(history.items || []);
    } catch (reason) {
      setError(reason.message || '대화를 불러오지 못했습니다.');
    } finally { setLoadingChat(false); }
  };

  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.allSettled([
      requestQuote('/chats?limit=100&offset=0'),
      requestQuote('/cards?limit=100&offset=0'),
      requestQuote('/chats/models'),
    ]).then(([chatResult, quoteResult, modelResult]) => {
      if (!alive) return;
      if (chatResult.status === 'fulfilled') setChats(chatResult.value.items || []);
      else setError(chatResult.reason.message || '대화 목록을 불러오지 못했습니다.');
      if (quoteResult.status === 'fulfilled') setQuotes((quoteResult.value.items || []).filter((quote) => (quote.item_count || 0) > 0 && quote.status !== 'extracting'));
      else setNotice(quoteResult.reason.message || '견적서 목록을 불러오지 못했습니다.');
      if (modelResult.status === 'fulfilled') {
        setModels(modelResult.value.items || []);
        setDefaultModel(modelResult.value.default_model || '');
        setChatModel(modelResult.value.default_model || '');
      } else setNotice((previous) => previous || modelResult.reason.message || '대화 모델 목록을 불러오지 못했습니다.');
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  useEffect(() => { messageEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, sending]);

  const startChat = async (event) => {
    event.preventDefault();
    if (!selectedQuotes.length || loadingChat) return;
    setLoadingChat(true); setError(''); setNotice('');
    try {
      const selected = quotes.filter((quote) => selectedQuotes.includes(quote.quote_id));
      const title = selected.map(displayQuote).join(', ').slice(0, 200);
      const created = await requestQuote('/chats', { method: 'POST', body: JSON.stringify({ quote_ids: selectedQuotes, title, ...(chatModel ? { model: chatModel } : {}) }) });
      await refreshChats();
      setActiveChat(created); setMessages([]); setCreating(false); setSelectedQuotes([]); setQuestion('');
      questionBox.current?.focus();
    } catch (reason) { setError(reason.message || '대화를 시작하지 못했습니다.'); }
    finally { setLoadingChat(false); }
  };

  const sendQuestion = async (event) => {
    event.preventDefault();
    const content = question.trim();
    if (!activeChat || !content || sending || activeChat.busy) return;
    setSending(true); setError(''); setQuestion('');
    try {
      const result = await requestQuote(`/chats/${encodeURIComponent(activeChat.chat_id)}/messages`, { method: 'POST', body: JSON.stringify({ content, expected_version: activeChat.version }) });
      setActiveChat(result.chat);
      setMessages((current) => [...current, result.user_message, result.assistant_message]);
      setChats((current) => [result.chat, ...current.filter((chat) => chat.chat_id !== result.chat.chat_id)]);
    } catch (reason) {
      setQuestion(content);
      setError(reason.message || '답변을 받지 못했습니다.');
      if (reason.message?.startsWith('409:')) {
        try { await loadChat(activeChat.chat_id); } catch { /* loadChat displays its own error */ }
      }
    } finally { setSending(false); }
  };

  const changeModel = async (model) => {
    if (!activeChat || activeChat.busy || sending || model === activeChat.model) return;
    setError('');
    try {
      const updated = await requestQuote(`/chats/${encodeURIComponent(activeChat.chat_id)}`, { method: 'PATCH', body: JSON.stringify({ model, expected_version: activeChat.version }) });
      setActiveChat(updated); setChatModel(updated.model);
      setChats((current) => current.map((chat) => chat.chat_id === updated.chat_id ? updated : chat));
    } catch (reason) { setError(reason.message || '모델을 변경하지 못했습니다.'); }
  };

  const deleteChat = async () => {
    if (!activeChat || deleting || !window.confirm('이 대화와 저장된 질문·답변·근거를 영구 삭제할까? 견적서 원본은 유지돼.')) return;
    setDeleting(true); setError('');
    try {
      await requestQuote(`/chats/${encodeURIComponent(activeChat.chat_id)}`, { method: 'DELETE' });
      setChats((current) => current.filter((chat) => chat.chat_id !== activeChat.chat_id));
      setActiveChat(null); setMessages([]); onNotify?.('대화를 삭제했어.');
    } catch (reason) { setError(reason.message || '대화를 삭제하지 못했습니다.'); }
    finally { setDeleting(false); }
  };

  const toggleQuote = (id) => setSelectedQuotes((current) => current.includes(id) ? current.filter((value) => value !== id) : current.length < 5 ? [...current, id] : current);
  const activeQuotes = (activeChat?.quote_ids || []).map((id) => quoteMap.get(id)).filter(Boolean);
  const usage = activeChat?.usage;

  return <section className="quote-chat-page">
    <aside className="quote-chat-sidebar">
      <div className="quote-chat-sidebar-heading"><div><span>QUOTE ASSISTANT</span><h1>견적서 AI</h1></div><button className="primary-button" type="button" disabled={sending} onClick={() => { setCreating(true); setActiveChat(null); setMessages([]); setSelectedQuotes([]); setError(''); setNotice(''); }}><Plus />새 대화</button></div>
      <div className="quote-chat-list-title">저장된 대화 <span>{loading ? '…' : chats.length}</span></div>
      <div className="quote-chat-list">{loading ? <p className="chat-sidebar-state"><LoaderCircle className="spin" />대화를 불러오는 중</p> : chats.length ? chats.map((chat) => <button type="button" key={chat.chat_id} disabled={sending} className={`quote-chat-list-item ${activeChat?.chat_id === chat.chat_id ? 'active' : ''}`} onClick={() => loadChat(chat.chat_id)}><MessageCircle /><span><b>{chatTitle(chat, quoteMap)}</b><small>{new Date(chat.updated_at).toLocaleDateString('ko-KR')}</small></span></button>) : <p className="chat-sidebar-state">아직 저장된 대화가 없어.</p>}</div>
    </aside>

    <div className="quote-chat-main">
      {error && <div className="quote-chat-error" role="alert"><span>{error}</span><button type="button" aria-label="오류 닫기" onClick={() => setError('')}><X /></button></div>}
      {notice && <div className="quote-chat-notice" role="status">{notice}<button type="button" aria-label="알림 닫기" onClick={() => setNotice('')}><X /></button></div>}

      {creating ? <form className="chat-create-view" onSubmit={startChat}>
        <div className="chat-view-heading"><div><span>NEW CONVERSATION</span><h2>어떤 견적서를 살펴볼까?</h2><p>견적서 1~5개를 선택해 질문을 시작해.</p></div><button type="button" className="chat-icon-button" aria-label="새 대화 취소" onClick={() => setCreating(false)}><X /></button></div>
        <div className="chat-create-controls"><label className="chat-quote-search"><FileText /><input value={quoteSearch} onChange={(event) => setQuoteSearch(event.target.value)} placeholder="견적번호, 거래처, 파일명 검색" aria-label="대화에 사용할 견적서 검색" /></label><label className="chat-model-select"><span>AI 모델</span><select value={chatModel || defaultModel} onChange={(event) => setChatModel(event.target.value)} disabled={!models.length}>{models.map((model) => <option key={model.id} value={model.id}>{model.name}{model.default ? ' · 기본' : ''}</option>)}</select><ChevronDown /></label></div>
        <div className="chat-quote-picker" role="group" aria-label="대화에 사용할 견적서 선택">{filteredQuotes.length ? filteredQuotes.map((quote) => <label className={`chat-quote-option ${selectedQuotes.includes(quote.quote_id) ? 'selected' : ''}`} key={quote.quote_id}><input type="checkbox" checked={selectedQuotes.includes(quote.quote_id)} disabled={!selectedQuotes.includes(quote.quote_id) && selectedQuotes.length >= 5} onChange={() => toggleQuote(quote.quote_id)} /><span className="chat-quote-option-copy"><b>{displayQuote(quote)}</b><small>{quote.customer_name || '거래처 미기재'} · {shortDate(quote.issue_date)} · {quote.item_count || 0}개 품목</small></span><strong>{money(quote.total_amount, quote.currency)}</strong></label>) : <div className="chat-empty">{quoteSearch ? '검색 결과가 없어.' : '대화에 사용할 수 있는 추출 완료 견적서가 없어.'}</div>}</div>
        <div className="chat-create-footer"><span>{selectedQuotes.length}/5개 선택</span><button type="submit" className="primary-button" disabled={!selectedQuotes.length || loadingChat}>{loadingChat ? <LoaderCircle className="spin" /> : <MessageCircle />}{loadingChat ? '시작 중' : '대화 시작'}</button></div>
      </form> : loadingChat ? <div className="chat-center-state"><LoaderCircle className="spin" />대화를 불러오는 중</div> : activeChat ? <>
        <header className="chat-conversation-heading"><div className="chat-heading-title"><span>QUOTATION CHAT</span><h2>{chatTitle(activeChat, quoteMap)}</h2><div className="chat-context-quotes">{activeQuotes.map((quote) => <span key={quote.quote_id}>{displayQuote(quote)}</span>)}{!activeQuotes.length && activeChat.quote_ids.map((id) => <span key={id}>{displayQuote({ quote_id: id })}</span>)}</div></div><div className="chat-heading-actions"><label className="chat-model-select compact"><span className="sr-only">AI 모델</span><select aria-label="대화 모델 선택" value={activeChat.model || defaultModel} disabled={activeChat.busy || sending || !models.length} onChange={(event) => changeModel(event.target.value)}>{models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}</select><ChevronDown /></label><button type="button" className="chat-icon-button danger" aria-label="대화 삭제" onClick={deleteChat} disabled={deleting || activeChat.busy}><Trash2 /></button></div></header>
        <div className="chat-message-area" aria-live="polite">{messages.length ? messages.map((message) => <article className={`chat-message ${message.role}`} key={message.message_id}><div className="chat-message-avatar">{message.role === 'assistant' ? <Bot /> : <UserRound />}</div><div className="chat-message-content"><div className="chat-message-label">{message.role === 'assistant' ? '견적서 AI' : '나'} <time>{new Date(message.created_at).toLocaleString('ko-KR', { dateStyle: 'short', timeStyle: 'short' })}</time></div><p>{message.content}</p>{message.role === 'assistant' && message.sources?.length > 0 && <details className="chat-sources"><summary><Check />답변 근거 {message.sources.length}개 보기</summary><ul>{message.sources.map((source, index) => <Citation key={`${source.quote_id}-${source.field_path}-${index}`} source={source} quoteMap={quoteMap} />)}</ul></details>}</div></article>) : <div className="chat-welcome"><span className="chat-welcome-icon"><Bot /></span><h3>견적서에 대해 물어봐.</h3><p>납기, 유효기간, 품목, 가격을 비교하고 답변 근거도 확인할 수 있어.</p><div className="chat-suggestions"><button type="button" onClick={() => { setQuestion('이 견적서의 주요 품목과 총액을 정리해줘.'); questionBox.current?.focus(); }}>주요 품목과 총액 정리</button><button type="button" onClick={() => { setQuestion('납기와 유효기간을 알려줘.'); questionBox.current?.focus(); }}>납기와 유효기간 확인</button></div></div>}{sending && <article className="chat-message assistant"><div className="chat-message-avatar"><Bot /></div><div className="chat-message-content"><div className="chat-message-label">견적서 AI</div><p className="chat-thinking"><LoaderCircle className="spin" />견적서를 확인하고 답변을 작성하고 있어.</p></div></article>}<div ref={messageEnd} /></div>
        <form className="chat-composer" onSubmit={sendQuestion}><textarea ref={questionBox} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="견적서에 대해 질문해줘. (Enter 전송, Shift+Enter 줄바꿈)" aria-label="질문 입력" maxLength={4000} disabled={sending || activeChat.busy} rows={2} /><button className="primary-button" type="submit" disabled={!question.trim() || sending || activeChat.busy} aria-label="질문 보내기">{sending || activeChat.busy ? <LoaderCircle className="spin" /> : <Send />}<span>보내기</span></button><small>AI 답변은 저장된 견적서 데이터와 근거를 바탕으로 생성돼. 답변은 원본과 함께 확인해줘.</small></form>
        {usage && <div className="chat-usage">이 대화 사용량 <b>{(usage.total_tokens || 0).toLocaleString('ko-KR')} 토큰</b>{usage.complete === false && <span>일부 토큰 사용량 미기록</span>}</div>}
      </> : <div className="chat-empty-view"><span className="chat-welcome-icon"><Bot /></span><h2>견적서 내용을 AI와 함께 살펴봐.</h2><p>선택한 견적서를 바탕으로 질문하고 답변의 근거를 확인할 수 있어.</p><button className="primary-button" type="button" onClick={() => { setCreating(true); setError(''); }}><Plus />새 대화 시작</button></div>}
    </div>
  </section>;
}
