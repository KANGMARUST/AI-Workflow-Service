import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
import { parseAnswerBlocks } from '../frontend/src/answerTables.js';

const cases = [
  () => {
    const blocks = parseAnswerBlocks('저장된 두 품목입니다.\n\n| 품목 | 원본 단가 | 근거 |\n| --- | ---: | :--- |\n| 브라켓 | 12,000원 | [1] |\n| 센서 | 미기재 | [2] |\n\n금액은 원본 기준입니다.');
    assert.deepEqual(blocks.map(block => block.type), ['text', 'table', 'text']);
    assert.deepEqual(blocks[1].headers, ['품목', '원본 단가', '근거']);
    assert.deepEqual(blocks[1].rows, [['브라켓', '12,000원', '[1]'], ['센서', '미기재', '[2]']]);
  },
  () => {
    const blocks = parseAnswerBlocks('품목 | 선택 조건\n--- | ---\nA\\|B | 선택 안 함');
    assert.deepEqual(blocks[0].rows, [['A|B', '선택 안 함']]);
  },
  () => {
    const input = '| 품목 | 금액 |\n| --- | --- |\n형식이 맞지 않는 행';
    assert.deepEqual(parseAnswerBlocks(input), [{ type: 'text', text: input }]);
  },
];

cases.forEach(run => run());
writeFileSync(new URL('./chat-table-results.json', import.meta.url), JSON.stringify({
  ok: true, tests_run: cases.length, live_api_called: false,
}, null, 2));
process.stdout.write(`Chat table checks: ${cases.length}/${cases.length} passed\n`);
