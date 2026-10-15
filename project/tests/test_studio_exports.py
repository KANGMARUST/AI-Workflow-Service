"""Validate actually exported Studio versions against server field contracts."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]/'agent_configs'/'studio_exports'
VERSIONS={'추출':3,'검토':2,'비교':2}


class ExportTests(unittest.TestCase):
    def test_saved_versions_and_structured_fields(self):
        for role,version in VERSIONS.items():
            doc=json.loads((ROOT/f'견적아카이브_{role}_v{version}.json').read_text(encoding='utf-8'))
            self.assertEqual(doc['exportedFrom']['configVer'],version)
            schemas=doc['workflowConfig']['informationExtractConfiguration']['schemas']
            self.assertGreaterEqual(len(schemas),3)
            names=[set(s['json_schema']['schema']['properties']) for s in schemas]
            expected={'추출':{'document_type','classification_reason','items_json','item_evidence_json','currency','tax_note'},
                      '검토':{'summary','review_level','issues','scope'},
                      '비교':{'summary','comparison_level','item_matches','conditions','scope'}}[role]
            self.assertTrue(all(expected<=name for name in names),role)
            if role=='추출':
                self.assertEqual(len(schemas),5)
                self.assertEqual(doc['workflowConfig']['pipelineType'],'classify-extract')
                for field in ('subtotal','tax','total','source_total'):
                    self.assertTrue(all(s['json_schema']['schema']['properties'][field]['type']=='string' for s in schemas))


if __name__=='__main__':unittest.main()
