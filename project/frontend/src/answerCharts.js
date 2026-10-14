const MEASURE = /(단가|금액|합계|총액|공급가액|세액|수량|비율|원가|가격|비용|매출|건수)/;
const DATE = /(날짜|작성일|견적일|발행일|일자|연도|시기|월별|월)/;

export function wantsVisualization(question) {
  return /(그래프|차트|시각화|시각적|시각 자료|도표|막대|꺾은선|그림으로|chart|graph|plot|visuali[sz])/i
    .test(question);
}

function numericCell(cell) {
  const value = cell.replace(/\s*\[\d+\]\s*$/, '').trim();
  const match = value.match(/^(₩|\$)?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(만원|천원|원|개|건|대|식|%|USD|KRW)?$/);
  if (!match) return null;
  const amount = Number(match[2].replaceAll(',', ''));
  const unit = match[3] || (match[1] === '₩' ? '원' : match[1] === '$' ? 'USD' : '');
  return Number.isFinite(amount) ? { value: amount, unit, display: value } : null;
}

function dateOrder(label) {
  const value = label.trim();
  const match = value.match(/^(\d{4})[-./](\d{1,2})(?:[-./](\d{1,2}))?$/) ||
    value.match(/^(\d{4})년\s*(\d{1,2})월(?:\s*(\d{1,2})일)?$/);
  if (!match) return null;
  const [, year, month, day = '1'] = match;
  const y = Number(year), m = Number(month), d = Number(day);
  return m >= 1 && m <= 12 && d >= 1 && d <= 31 ? y * 10000 + m * 100 + d : null;
}

export function chartFromTable(table) {
  if (table.type !== 'table' || table.rows.length < 2) return null;
  const labelColumn = table.headers.findIndex(header => DATE.test(header));
  const labelIndex = labelColumn >= 0 ? labelColumn : 0;
  const measureIndex = table.headers.findIndex((header, index) => index !== labelIndex && MEASURE.test(header));
  if (measureIndex < 0) return null;
  const points = table.rows.map(row => ({ label: row[labelIndex], number: numericCell(row[measureIndex]) }))
    .filter(point => point.label && point.number);
  if (points.length < 2 || new Set(points.map(point => point.number.unit)).size !== 1) return null;
  const dated = labelColumn >= 0 && points.every(point => dateOrder(point.label) !== null);
  if (dated) points.sort((a, b) => dateOrder(a.label) - dateOrder(b.label));
  const limit = dated ? 8 : 12;
  return {
    kind: dated ? 'line' : 'bar',
    title: `${table.headers[measureIndex]} ${dated ? '추이' : '비교'}`,
    unit: points[0].number.unit,
    points: points.slice(0, limit).map(point => ({
      label: point.label, value: point.number.value, display: point.number.display,
    })),
    omitted: table.rows.length - Math.min(points.length, limit),
  };
}
