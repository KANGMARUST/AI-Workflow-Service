"""Local comparison regression using invented quotes and an isolated archive DB."""
import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / 'backend' / '.packages'
if PACKAGES.exists():
    sys.path.insert(0, str(PACKAGES))
sys.path.insert(0, str(ROOT / 'backend'))
RUNS = ROOT / 'tests' / '.runs'
RUNS.mkdir(exist_ok=True)
TEMP = tempfile.TemporaryDirectory(prefix='similarity-', dir=RUNS)
os.environ['QUOTE_DATA_DIR'] = TEMP.name
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(TEMP.name) / 'quotes.db').as_posix()

import domain as d
from app import similar, compare_saved
from quote_similarity import compare_pair, recommend


def item(name='브라켓', specification='M20', unit='개', quantity=10, unit_price=100, **extra):
    row=dict(name=name, specification=specification, unit=unit, quantity=quantity,
                unit_price=unit_price, amount=None, is_component=False, parent_index=None,
                option_group='', original_text='')
    row.update(extra)
    return row


def quote(ident, when='2025-01-01', items=None, **extra):
    return dict(id=ident, source_name=ident + '.pdf', source_url='/api/files/' + ident,
                issue_date=when, currency='KRW', tax_note='VAT 별도', delivery='2주',
                payment_terms='30일', customer='가상 거래처', items=items or [item()], **extra)


class SimilarityTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        d.engine.dispose()
        TEMP.cleanup()
    def test_price_and_zero_baseline(self):
        before = quote('before')
        now = quote('now', '2026-01-01', [item(unit_price=120)])
        row = compare_pair(now, before)['rows'][0]
        self.assertEqual((row['status'], row['delta'], row['percent']), ('comparable', 20, 20))
        before['items'][0]['unit_price'] = 0
        row = compare_pair(now, before)['rows'][0]
        self.assertEqual((row['status'], row['delta'], row['percent']), ('comparable', 120, None))

    def test_conditions_and_missing_values(self):
        before = quote('before')
        for field, value, expected in [('specification','M30','review'),('unit','세트','incompatible'),
                                       ('quantity',20,'review'),('unit_price',None,'review')]:
            now = quote('now', '2026-01-01', [item(**{field:value})])
            row = compare_pair(now, before)['rows'][0]
            self.assertEqual(row['status'], expected, field)
            self.assertIsNone(row['delta'])
        now = quote('now','2026-01-01')
        now['currency'] = 'USD'
        self.assertEqual(compare_pair(now,before)['rows'][0]['status'],'incompatible')
        now['currency'] = 'KRW';now['tax_note'] = 'VAT 포함'
        self.assertEqual(compare_pair(now,before)['rows'][0]['status'],'review')
        now['tax_note'] = ''
        self.assertEqual(compare_pair(now,before)['rows'][0]['status'],'review')

    def test_options_components_and_ambiguity(self):
        before = quote('before', items=[item(), item(name='선택형', option_group='A')])
        now = quote('now','2026-01-01',[item(name='선택형',option_group='B')])
        report = compare_pair(now,before)
        self.assertEqual(report['rows'][0]['status'],'review')
        self.assertTrue(all(row['delta'] is None for row in report['rows']))
        package_before = quote('package-before',items=[item(name='장비'),item(name='모듈',is_component=True,parent_index=0)])
        package_now = quote('package-now','2026-01-01',[item(name='모듈')])
        self.assertNotEqual(compare_pair(package_now,package_before)['rows'][0]['status'],'comparable')
        ambiguous = quote('ambiguous',items=[item(),item()])
        row = compare_pair(quote('now','2026-01-01'),ambiguous)['rows'][0]
        self.assertEqual(row['status'],'review')
        self.assertEqual(row['candidates'],[2,1])
        confirmed = next(row for row in compare_pair(quote('now','2026-01-01'),ambiguous,{0:0})['rows'] if row['current'])
        self.assertEqual(confirmed['status'],'comparable')

    def test_recommendation_dates_duplicates_trash_and_no_candidates(self):
        current=quote('current','2026-01-01')
        current['source_url']='/api/files/same.pdf'
        unrelated=quote('unrelated',items=[item(name='케이블')])
        duplicate=quote('duplicate');duplicate['source_url']=current['source_url']
        deleted=quote('deleted');deleted['deleted_at']='2026-01-02'
        undated=quote('undated','')
        past=quote('past')
        result=recommend(current,[current,unrelated,duplicate,deleted,undated,past])
        self.assertEqual([r['id'] for r in result],['past','undated'])
        self.assertEqual([r['chronology'] for r in result],['past','unconfirmed'])
        self.assertEqual(recommend(current,[unrelated,duplicate,deleted]),[])

    def test_read_only_api_and_originals(self):
        ids=[]
        for marker, when, price in [('old','2025-01-01',100),('new','2026-01-01',120)]:
            content=('invented '+marker).encode()
            digest=hashlib.sha256(content).hexdigest()
            (Path(TEMP.name)/'files'/f'{digest}.pdf').write_bytes(content)
            q=d.empty_quote(dict(source_name=marker+'.pdf',source_url='/api/files/'+digest+'.pdf',
                                 issue_date=when,customer='가상 거래처',currency='KRW',tax_note='VAT 별도',items=[item(unit_price=price)]))
            d.save(q,digest=digest);ids.append(q['id'])
        original=(Path(TEMP.name)/'quotes.db').stat().st_size
        candidates=similar(ids[1])
        self.assertEqual([c['id'] for c in candidates],[ids[0]])
        result=compare_saved(ids[1],ids[0])
        self.assertEqual(result['rows'][0]['delta'],20)
        self.assertEqual((Path(TEMP.name)/'quotes.db').stat().st_size,original)
        self.assertEqual(len(d.all_quotes()),2)
        self.assertTrue(all((Path(TEMP.name)/'files'/Path(q['source_url']).name).exists() for q in d.all_quotes()))


if __name__ == '__main__':
    unittest.main()
