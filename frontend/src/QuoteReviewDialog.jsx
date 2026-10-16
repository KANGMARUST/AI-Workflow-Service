import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Download, LoaderCircle, Save, X } from 'lucide-react';
import { requestQuote } from './quoteApi.js';
import './QuoteReviewDialog.css';

const basicFields = [
  ['quote_number', '견적번호'], ['title', '제목'], ['issuer_company', '발행 회사'], ['customer_name', '거래처'],
  ['contact_name', '담당자'], ['contact_phone', '연락처'], ['contact_email', '이메일'],
  ['issue_date', '작성일', 'date'], ['valid_until', '유효기한', 'date'], ['delivery_date', '납기일', 'date'],
];
const moneyFields = [['currency', '통화'], ['subtotal', '공급가액', 'number'], ['tax_amount', '세액', 'number'], ['total_amount', '총액', 'number'], ['tax_rate', '세율', 'number']];
const conditionFields = [['tax_terms', '세금 조건'], ['discount_terms', '할인 조건'], ['payment_terms', '결제 조건'], ['delivery_terms', '납품 조건'], ['notes', '비고'], ['review_note', '검토 메모']];
const itemFields = [['item_name', '품목명'], ['specification', '규격'], ['unit', '단위'], ['quantity', '수량', 'number'], ['unit_price', '단가', 'number'], ['amount', '금액', 'number'], ['currency', '통화']];
const editableFields = [...basicFields, ...moneyFields, ...conditionFields, ['tax_basis']];
const statusNames = { review_required: '검토 미완료', confirmed: '검토 완료', extracting: '추출 중', rejected: '반려', archived: '보관' };
const text = (value) => value == null ? '' : String(value);
const nullable = (value) => value.trim() || null;

function makeForm(quote) {
  return {
    ...Object.fromEntries(editableFields.map(([key]) => [key, text(quote[key])])),
    items: (quote.items || []).map((item) => Object.fromEntries(itemFields.map(([key]) => [key, text(item[key])]))),
  };
}

export default function QuoteReviewDialog({ quoteId, onClose, onSaved, onNotify }) {
  const dialog = useRef(null);
  const errorBox = useRef(null);
  const busy = useRef(false);
  const [quote, setQuote] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [reload, setReload] = useState(0);
  const dirty = quote && form && JSON.stringify(form) !== JSON.stringify(makeForm(quote));
  const canEdit = quote?.status === 'review_required';

  useEffect(() => {
    if (error) errorBox.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [error, loading]);

  useEffect(() => {
    const element = dialog.current;
    const previousFocus = document.activeElement;
    element.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      element.close();
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setAcknowledged(false);
    requestQuote(`/quotes/${encodeURIComponent(quoteId)}`, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) { setQuote(data); setForm(makeForm(data)); } })
      .catch((reason) => { if (!controller.signal.aborted) setError(reason.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [quoteId, reload]);

  const close = () => {
    if (busy.current) return;
    if (dirty && !window.confirm('저장하지 않은 수정 내용이 있습니다. 닫을까요?')) return;
    onClose();
  };
  const update = (key, value) => { setForm((current) => ({ ...current, [key]: value })); setAcknowledged(false); };
  const updateItem = (index, key, value) => {
    setForm((current) => ({ ...current, items: current.items.map((item, i) => i === index ? { ...item, [key]: value } : item) }));
    setAcknowledged(false);
  };

  const save = async (event) => {
    event.preventDefault();
    if (busy.current || !dirty || !canEdit) return;
    busy.current = true; setSaving(true); setError('');
    try {
      const original = makeForm(quote);
      const changes = Object.fromEntries(editableFields.filter(([key]) => form[key] !== original[key]).map(([key]) => [key, nullable(form[key])]));
      if (JSON.stringify(form.items) !== JSON.stringify(original.items)) {
        changes.items = form.items.map((item, index) => {
          const { item_id, line_number, ...originalItem } = quote.items[index];
          return { ...originalItem, ...Object.fromEntries(itemFields.map(([key]) => [key, nullable(item[key])])) };
        });
      }
      const saved = await requestQuote(`/edit/${encodeURIComponent(quoteId)}`, { method: 'PATCH', body: JSON.stringify({ ...changes, expected_version: quote.version }) });
      setQuote(saved); setForm(makeForm(saved)); setAcknowledged(false);
      onSaved(); onNotify('수정 내용을 저장했습니다. 확인 사항을 검토한 뒤 검토 완료해 주세요.');
    } catch (reason) { setError(reason.message); }
    finally { busy.current = false; setSaving(false); }
  };

  const complete = async () => {
    if (busy.current || dirty || !acknowledged || !canEdit) return;
    busy.current = true; setSaving(true); setError('');
    try {
      const saved = await requestQuote(`/status/${encodeURIComponent(quoteId)}`, { method: 'POST', body: JSON.stringify({ status: 'confirmed', expected_version: quote.version }) });
      setQuote(saved); setForm(makeForm(saved));
      dialog.current?.scrollTo({ top: 0, behavior: 'smooth' });
      onSaved(); onNotify('검토 완료로 저장했습니다.');
    } catch (reason) { setError(reason.message); }
    finally { busy.current = false; setSaving(false); }
  };

  const download = async () => {
    if (downloading) return;
    setDownloading(true); setError('');
    try {
      const blob = await requestQuote(`/quotes/${encodeURIComponent(quoteId)}/source`, { download: true });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = quote.source_filename || '견적서'; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason) { setError(reason.message); }
    finally { setDownloading(false); }
  };

  const renderField = ([key, label, type = 'text']) => <label key={key}>{label}<input type={type} value={form[key]} onChange={(event) => update(key, event.target.value)} min={type === 'number' ? '0' : undefined} step={type === 'number' ? '0.0001' : undefined} maxLength={key === 'currency' ? 3 : undefined} pattern={key === 'currency' ? '[A-Z]{3}' : undefined} placeholder={key === 'currency' ? 'KRW' : undefined} /></label>;

  return <dialog ref={dialog} className="quote-review-dialog" aria-labelledby="quote-review-title" onCancel={(event) => { event.preventDefault(); close(); }}>
    <header className="quote-review-heading"><div><span className="quote-review-eyebrow">QUOTATION REVIEW</span><h2 id="quote-review-title">견적서 검토</h2><p>{quote?.source_filename || '견적서 상세 내용을 확인해 주세요.'}</p></div><button type="button" className="quote-review-close" aria-label="검토 창 닫기" disabled={saving} onClick={close}><X /></button></header>
    {loading ? <div className="quote-review-state" role="status"><LoaderCircle className="spin" />견적서를 불러오고 있습니다.</div> : <>
      {error && <div ref={errorBox} className="quote-review-error" role="alert"><span>{error}</span><button type="button" disabled={saving} onClick={() => { if (!dirty || window.confirm('수정 내용을 버리고 최신 정보를 불러올까요?')) setReload((value) => value + 1); }}>최신 정보 다시 불러오기</button></div>}
      {quote && form && <form onSubmit={save}>
        <div className="quote-review-body">
          <div className="quote-review-summary"><span className={`status-pill ${quote.status === 'confirmed' ? 'complete' : 'pending'}`}>{statusNames[quote.status] || quote.status}</span><button type="button" className="secondary-button" disabled={downloading || saving} onClick={download}>{downloading ? <LoaderCircle className="spin" /> : <Download />}원본 다운로드</button></div>
          {quote.status === 'confirmed' && <p className="quote-review-success" role="status"><CheckCircle2 />검토 완료된 견적서입니다.</p>}
          {!canEdit && quote.status !== 'confirmed' && <p className="quote-review-hint">현재 상태에서는 내용을 확인할 수 있습니다. 추출 중인 견적서는 추출 완료 후 검토해 주세요.</p>}
          <fieldset disabled={saving || !canEdit}><legend>기본 정보</legend><div className="quote-review-grid">{basicFields.map(renderField)}</div></fieldset>
          <fieldset disabled={saving || !canEdit}><legend>품목 <small>{form.items.length}개 · 금액은 원본 기준으로 확인해 주세요.</small></legend>
            {form.items.length ? <div className="quote-review-items"><table><thead><tr><th scope="col">번호</th>{itemFields.map(([key, label]) => <th scope="col" key={key}>{label}</th>)}</tr></thead><tbody>{form.items.map((item, index) => <tr key={index}><th scope="row">{index + 1}</th>{itemFields.map(([key, label, type = 'text']) => <td key={key}><input aria-label={`품목 ${index + 1} ${label}`} type={type} required={key === 'item_name'} maxLength={key === 'item_name' ? 500 : key === 'currency' ? 3 : undefined} pattern={key === 'item_name' ? '.*\\S.*' : key === 'currency' ? '[A-Z]{3}' : undefined} min={type === 'number' ? '0' : undefined} step={type === 'number' ? '0.0001' : undefined} value={item[key]} onChange={(event) => updateItem(index, key, event.target.value)} /></td>)}</tr>)}</tbody></table></div> : <p className="quote-review-hint">추출된 품목이 없습니다. 원본 파일을 확인해 주세요.</p>}
          </fieldset>
          <fieldset disabled={saving || !canEdit}><legend>금액 및 조건</legend><div className="quote-review-grid">{moneyFields.map(renderField)}<label>세금 포함 여부<select value={form.tax_basis} onChange={(event) => update('tax_basis', event.target.value)}><option value="">미기재</option><option value="exclusive">세금 별도</option><option value="inclusive">세금 포함</option></select></label>{conditionFields.map(([key, label]) => <label key={key}>{label}<textarea rows={2} value={form[key]} onChange={(event) => update(key, event.target.value)} maxLength={10000} /></label>)}</div></fieldset>
          <section className="quote-review-warnings" aria-label="검토 확인 사항"><h3>확인 사항 {quote.validation?.warnings?.length || 0}건</h3><p>저장된 내용 기준입니다. 수정했다면 먼저 저장한 뒤 다시 확인해 주세요.</p>{quote.validation?.warnings?.length ? <ul>{quote.validation.warnings.map((warning, index) => <li key={index}>{warning.message}</li>)}</ul> : <p>자동 검사에서 발견한 확인 사항이 없습니다. 원본과 내용을 대조해 주세요.</p>}</section>
          {canEdit && <label className="quote-review-ack"><input type="checkbox" checked={acknowledged} disabled={saving || dirty} onChange={(event) => setAcknowledged(event.target.checked)} />원본과 견적 정보·품목·금액 및 확인 사항을 검토했습니다.</label>}
        </div>
        <footer className="quote-review-footer"><p role="status">{dirty ? '수정 내용을 먼저 저장해 주세요.' : canEdit ? '검토 확인란을 선택하면 완료할 수 있습니다.' : '저장된 견적서 내용입니다.'}</p><div><button type="button" className="secondary-button" disabled={saving} onClick={close}>닫기</button>{canEdit && <><button type="submit" className="secondary-button" disabled={saving || !dirty}>{saving ? <LoaderCircle className="spin" /> : <Save />}수정 저장</button><button type="button" className="primary-button" disabled={saving || dirty || !acknowledged} onClick={complete}>{saving ? <LoaderCircle className="spin" /> : <CheckCircle2 />}검토 완료</button></>}</div></footer>
      </form>}
    </>}
  </dialog>;
}
