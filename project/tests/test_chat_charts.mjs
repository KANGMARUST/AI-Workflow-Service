import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import { parseAnswerBlocks } from '../frontend/src/answerTables.js';
import { chartFromTable, wantsVisualization } from '../frontend/src/answerCharts.js';

const table = answer => parseAnswerBlocks(answer).find(block => block.type === 'table');
const cases = [
  () => {
    assert.equal(wantsVisualization('브라켓 단가를 견적별로 비교해줘'), false);
    assert.equal(wantsVisualization('브라켓 단가를 표로 보여줘'), false);
    assert.equal(wantsVisualization('브라켓 단가를 그래프로 보여줘'), true);
    assert.equal(wantsVisualization('월별 원본 단가 추이를 보여줘'), false);
    assert.equal(wantsVisualization('월별 원본 단가 추이를 그래프로 보여줘'), true);
  },
  () => {
    const chart = chartFromTable(table('| 품목 | 원본 단가 | 근거 |\n| --- | ---: | --- |\n| 브라켓 | 12,000원 | [1] |\n| 모터 | 15,000원 | [2] |\n| 센서 | 미기재 | [3] |'));
    assert.equal(chart.kind, 'bar');
    assert.deepEqual(chart.points.map(point => point.value), [12000, 15000]);
    assert.equal(chart.omitted, 1);
  },
  () => {
    const chart = chartFromTable(table('| 작성일 | 원본 단가 |\n| --- | --- |\n| 2026-10-02 | 13,000원 |\n| 2026-09-01 | 12,000원 |'));
    assert.equal(chart.kind, 'line');
    assert.deepEqual(chart.points.map(point => point.label), ['2026-09-01', '2026-10-02']);
  },
  () => {
    assert.equal(chartFromTable(table('| 품목 | 금액 |\n| --- | --- |\n| A | 10원 |\n| B | 20USD |')), null);
    assert.equal(chartFromTable(table('| 품목 | 조건 |\n| --- | --- |\n| A | 즉시 |\n| B | 협의 |')), null);
  },
];

cases.forEach(run => run());
writeFileSync(new URL('./chat-chart-results.json', import.meta.url), JSON.stringify({
  ok: true, tests_run: cases.length, live_api_called: false,
}, null, 2));
process.stdout.write(`Chat chart checks: ${cases.length}/${cases.length} passed\n`);
