import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, MessageSquareText, Plus, Sparkles, Trash2 } from 'lucide-react';
import { api } from './api';
import { CHAT_MODELS, DEFAULT_CHAT_MODEL } from './chatModels';
import { parseAnswerBlocks } from './answerTables';
import { chartFromTable, wantsVisualization } from './answerCharts';

const STORAGE_KEY = 'quote-archive-chat-v1';

function loadThreads() {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(value)) return [];
    return value.filter(thread => thread && typeof thread.id === 'string' &&
      typeof thread.title === 'string' && Array.isArray(thread.messages))
      .slice(0, 20).map(thread => ({
        id: thread.id,
        title: thread.title.slice(0, 60),
        messages: thread.messages.filter(message => message &&
          ['user', 'assistant', 'error'].includes(message.role) &&
          typeof message.content === 'string').slice(-40),
      }));
  } catch { return []; }
}

function sourceLabel(quote) {
  return quote.project_name || quote.source_name || quote.number || '제목 미기재';
}

function tokenCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function AnswerChart({ chart }) {
  const max = Math.max(...chart.points.map(point => point.value), 1);
  return <figure className="chat-chart" aria-label={chart.title}>
    <figcaption>{chart.title}{chart.unit && <span> · 단위 {chart.unit}</span>}</figcaption>
    {chart.kind === 'bar' ? <div className="chat-chart-bars">{chart.points.map((point, index) =>
      <div className="chat-chart-bar-row" key={`${point.label}-${index}`}>
        <span title={point.label}>{point.label}</span>
        <div className="chat-chart-track"><div style={{ width: `${point.value / max * 100}%` }}/></div>
        <strong>{point.display}</strong>
      </div>)}</div> : <div className="chat-chart-line-scroll"><svg viewBox="0 0 620 230" role="img" aria-label={`${chart.title}: ${chart.points.map(point => `${point.label} ${point.display}`).join(', ')}`}>
      <line x1="56" y1="172" x2="580" y2="172" stroke="#c9d9d2"/>
      <polyline fill="none" stroke="#159a82" strokeWidth="3" strokeLinejoin="round" points={chart.points.map((point, index) =>
        `${56 + index * 524 / (chart.points.length - 1)},${172 - point.value / max * 125}`).join(' ')}/>
      {chart.points.map((point, index) => { const x = 56 + index * 524 / (chart.points.length - 1), y = 172 - point.value / max * 125;
        return <g key={`${point.label}-${index}`}><circle cx={x} cy={y} r="5" fill="#159a82"><title>{point.label}: {point.display}</title></circle>
          <text x={x} y={Math.max(y - 11, 20)} textAnchor="middle" className="chat-chart-value">{point.display}</text>
          <text x={x} y="198" textAnchor="middle" className="chat-chart-label">{point.label.length > 12 ? `${point.label.slice(0, 11)}…` : point.label}</text></g>; })}
    </svg></div>}
    {chart.omitted > 0 && <p>그래프에 표시하지 않은 행 {chart.omitted}개는 위 표에서 확인해줘.</p>}
    <small>AI 답변의 표를 시각화했어. 값과 조건은 원본 문서로 확인해줘.</small>
  </figure>;
}

function AnswerTable({ block, visualize }) {
  const chart = visualize ? chartFromTable(block) : null;
  return <><div className="chat-table-scroll"><table className="chat-data-table">
    <thead><tr>{block.headers.map((header, column) => <th scope="col" key={column}>{header}</th>)}</tr></thead>
    <tbody>{block.rows.map((row, number) => <tr key={number}>{row.map((cell, column) =>
      <td key={column}>{cell}</td>)}</tr>)}</tbody>
  </table></div>{chart && <AnswerChart chart={chart}/>}</>;
}

function AnswerContent({ content, visualize }) {
  return <div className="chat-answer">{parseAnswerBlocks(content).map((block, index) =>
    block.type === 'table' ? <AnswerTable block={block} visualize={visualize} key={index}/> :
    <p className="chat-answer-text" key={index}>{block.text}</p>)}</div>;
}

export default function NaturalChat({ settings, open, configure, selectModel }) {
  const [threads, setThreads] = useState(loadThreads);
  const [activeId, setActiveId] = useState(() => loadThreads()[0]?.id || null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);
  const current = threads.find(thread => thread.id === activeId);
  const usedTokens = threads.reduce((total, thread) => total + thread.messages.reduce(
    (sum, message) => sum + (tokenCount(message.usage?.total_tokens) || 0), 0), 0);

  useEffect(() => {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(threads.slice(0, 20))); }
    catch { /* Conversation remains available until this tab is closed. */ }
  }, [threads]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ block: 'end' }); }, [activeId, current?.messages.length]);

  function newChat() { if (!sending) { setActiveId(null); setInput(''); } }
  function removeChat(id) {
    if (sending || !window.confirm('이 탭에 저장된 이 대화를 지울까요?')) return;
    setThreads(previous => previous.filter(thread => thread.id !== id));
    if (activeId === id) setActiveId(null);
  }

  async function send(event) {
    event.preventDefault();
    const question = input.trim();
    if (!question || sending) return;
    const visualRequested = wantsVisualization(question);
    const id = activeId || crypto.randomUUID();
    const previousMessages = current?.messages || [];
    const history = previousMessages.filter(message => message.role !== 'error')
      .slice(-8).map(message => ({ role: message.role, content: message.content.slice(0, 2000) }));
    const userMessage = { role: 'user', content: question };
    setThreads(previous => {
      const existing = previous.find(thread => thread.id === id);
      if (existing) return previous.map(thread => thread.id === id ?
        { ...thread, messages: [...thread.messages, userMessage].slice(-40) } : thread);
      return [{ id, title: question.slice(0, 38), messages: [userMessage] }, ...previous].slice(0, 20);
    });
    setActiveId(id);
    setInput('');
    setSending(true);
    try {
      const result = await api('/natural-search', {
        method: 'POST',
        body: JSON.stringify({ question, history: settings.enabled ? history : [],
          model: settings.chatModel || DEFAULT_CHAT_MODEL }),
        ai: settings.enabled ? settings : undefined,
      });
      const assistantMessage = {
        role: 'assistant', content: result.answer, scopeNote: result.scope_note || '',
        sources: (result.quotes || []).map(quote => ({ id: quote.id, label: sourceLabel(quote) })),
        method: result.method, model: result.model, usage: result.usage, visualRequested,
      };
      setThreads(previous => previous.map(thread => thread.id === id ?
        { ...thread, messages: [...thread.messages, assistantMessage].slice(-40) } : thread));
    } catch (error) {
      setThreads(previous => previous.map(thread => thread.id === id ?
        { ...thread, messages: [...thread.messages, { role: 'error', content: error.message }].slice(-40) } : thread));
    } finally { setSending(false); }
  }

  return <section className="chat-shell" aria-label="견적 대화">
    <aside className="chat-history">
      <button className="chat-new" onClick={newChat} disabled={sending}><Plus size={17}/>새 대화</button>
      <div className="chat-history-label">이 탭의 이전 대화</div>
      <div className="chat-thread-list">
        {threads.map(thread => <div className={'chat-thread' + (thread.id === activeId ? ' active' : '')} key={thread.id}>
          <button className="chat-thread-open" onClick={() => setActiveId(thread.id)} disabled={sending} title={thread.title}>
            <MessageSquareText size={15}/><span>{thread.title}</span>
          </button>
          <button className="chat-thread-delete" aria-label={`${thread.title} 대화 삭제`} title="대화 삭제" onClick={() => removeChat(thread.id)} disabled={sending}><Trash2 size={14}/></button>
        </div>)}
        {!threads.length && <p className="chat-history-empty">대화가 아직 없어.</p>}
      </div>
      <p className="chat-storage-note">질문과 답변은 이 탭에만 남아. 탭을 닫으면 기록이 지워져.</p>
    </aside>
    <div className="chat-main">
      <div className="chat-statusbar">
        {settings.enabled ? <label>답변 모델 <select aria-label="답변 모델" value={settings.chatModel || DEFAULT_CHAT_MODEL}
          onChange={event => selectModel(event.target.value)} disabled={sending}>
          {CHAT_MODELS.map(model => <option key={model.id} value={model.id}>{model.label}</option>)}
        </select></label> : <button className="text-button" onClick={configure}>내 API 연결하기</button>}
        <span>이 탭에 남은 대화의 사용량: {usedTokens.toLocaleString()} 토큰</span>
        <a href="https://console.upstage.ai/billing" target="_blank" rel="noreferrer">남은 크레딧 확인 ↗</a>
      </div>
      <div className="chat-scroll" role="log" aria-live="polite">
        {!current?.messages.length ? <div className="chat-welcome">
          <span className="chat-welcome-icon"><Sparkles size={25}/></span>
          <h2>보관된 견적에 관해 물어봐</h2>
          <p>저장된 견적을 근거로 답하고, 사용한 문서를 함께 보여줄게.</p>
          <div className="chat-examples"><span>예시 질문</span><p>“브라켓 단가가 어떻게 달라졌어?”</p><p>“월별 원본 단가 추이를 그래프로 보여줘”</p></div>
        </div> : current.messages.map((message, index) => <div className={'chat-message ' + message.role} key={`${current.id}-${index}`}>
          {message.role !== 'user' && <span className="chat-avatar"><Sparkles size={17}/></span>}
          <div className="chat-message-body">
            <div className="chat-message-label">{message.role === 'user' ? '나' : message.role === 'error' ? '오류' : '견적 아카이브 AI'}</div>
            {message.role === 'assistant' ? <AnswerContent content={message.content}
              visualize={message.visualRequested ?? wantsVisualization(current.messages[index - 1]?.content || '')}/> : <p>{message.content}</p>}
            {message.scopeNote && <small className="chat-scope">{message.scopeNote}</small>}
            {tokenCount(message.usage?.total_tokens) !== null && <small className="chat-usage">
              {CHAT_MODELS.find(model => model.id === message.model)?.label || 'Solar'} · 이 답변 {message.usage.total_tokens.toLocaleString()} 토큰
              {tokenCount(message.usage.prompt_tokens) !== null && tokenCount(message.usage.completion_tokens) !== null &&
                ` (입력 ${message.usage.prompt_tokens.toLocaleString()} / 출력 ${message.usage.completion_tokens.toLocaleString()})`}
            </small>}
            {!!message.sources?.length && <div className="chat-sources"><strong>참고 문서</strong>{message.sources.map((source, i) =>
              <button key={`${source.id}-${i}`} onClick={() => open(source.id)}>[{i + 1}] {source.label}</button>)}</div>}
          </div>
        </div>)}
        {sending && <div className="chat-message assistant"><span className="chat-avatar"><Sparkles size={17}/></span><div className="chat-message-body"><div className="chat-message-label">견적 아카이브 AI</div><p className="chat-thinking">저장된 견적을 확인하는 중...</p></div></div>}
        <div ref={bottomRef}/>
      </div>
      <div className="chat-composer-wrap">
        <form className="chat-composer" onSubmit={send}>
          <textarea aria-label="견적 질문 입력" rows={2} maxLength={1000} placeholder="저장된 견적에 대해 질문해줘" value={input}
            onChange={event => setInput(event.target.value)} onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); }
            }}/>
          <button type="submit" aria-label="질문 보내기" disabled={!input.trim() || sending}><ArrowUp size={19}/></button>
        </form>
        <p className="chat-mode-note">{settings.enabled ?
          '본인 Upstage API 사용 중 · 질문, 최근 대화와 관련 저장 정보가 전송돼. 표시된 토큰은 계정 전체 사용량이나 잔여 크레딧이 아니야.' :
          '로컬 조건 검색 중 · API 설정에서 본인 키를 적용하면 후속 질문까지 이어서 답할 수 있어.'}</p>
      </div>
    </div>
  </section>;
}
