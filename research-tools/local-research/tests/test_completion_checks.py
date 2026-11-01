import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('completion_checks',Path(__file__).resolve().parents[1]/'services/completion_checks.py')
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
TEXT='The committee reviewed the public revenue and expenditure accounts.'

class CompletionTests(unittest.TestCase):
    def test_printed_table_leaders_are_not_a_generation_loop(self):
        self.assertFalse(checks.excessive_repetition('The State'+'.'*60+'4,821,550'))
        self.assertFalse(checks.excessive_repetition('Adams'+'-'*75+'67,058'))
        self.assertTrue(checks.excessive_repetition('0'*150))
        self.assertTrue(checks.excessive_repetition('π'*150))
        self.assertTrue(checks.excessive_repetition('.'*2048))
    def test_compaction_preserves_table_cells_spans_and_text(self):
        source = '<table style="' + 'padding:0;'*500 + '"><tr><td rowspan="2" style="color:red">A 12</td><td colspan="3">B 34</td></tr></table>'
        compact = checks.compact_markup(source)
        self.assertLess(len(compact), 150)
        self.assertIn('rowspan="2"', compact)
        self.assertIn('colspan="3"', compact)
        from bs4 import BeautifulSoup
        self.assertEqual(BeautifulSoup(source,'html.parser').get_text(' '), BeautifulSoup(compact,'html.parser').get_text(' '))
        self.assertIn('<table>', compact)

    def test_normal_completion_is_not_rejected(self):
        self.assertEqual(checks.completion_flags(TEXT,[{'finish_reason':'stop'}]),[])
    def test_token_limit_and_missing_reason_fail(self):
        for calls in [[],[{'finish_reason':'length'}],[{}]]:
            self.assertIn('Recognition did not explicitly finish normally',checks.completion_flags(TEXT,calls))
    def test_repetition_and_unclosed_table_fail(self):
        self.assertIn('Excessive repeated text',checks.completion_flags('abcdef '*30,[{'finish_reason':'stop'}]))
        self.assertIn('Unclosed table',checks.completion_flags('<TABLE><tr><td>'+TEXT,[{'finish_reason':'stop'}]))
