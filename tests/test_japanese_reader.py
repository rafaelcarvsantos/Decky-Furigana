import ast
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'py_modules'))

from japanese_reader import JapaneseReader, reading_spans, span_rect
from providers.base import TextRegion, ProviderType
from providers.chromescreenai_protos import chrome_screen_ai_pb2 as proto
from providers.chromescreenai_subprocess import _proto_to_regions
from providers.japanese_service import JapaneseService


def line_region(text):
    return {'text': text, 'rect': {'left': 10, 'top': 50, 'right': 10 + len(text) * 20, 'bottom': 75},
            'symbols': [{'text': c, 'start': i, 'end': i + 1,
                         'rect': {'left': 10 + i * 20, 'top': 50, 'right': 30 + i * 20, 'bottom': 75}}
                        for i, c in enumerate(text)]}


class AlignmentTests(unittest.TestCase):
    def test_okurigana_is_not_repeated_above_kanji(self):
        self.assertEqual(reading_spans('食べる', 'タベル'), [{'start': 0, 'end': 1, 'reading': 'た'}])

    def test_compound_reading_stays_over_whole_compound(self):
        self.assertEqual(reading_spans('今日', 'キョウ'), [{'start': 0, 'end': 2, 'reading': 'きょう'}])

    def test_multiple_kanji_runs(self):
        self.assertEqual([s['reading'] for s in reading_spans('取り扱う', 'トリアツカウ')], ['と', 'あつか'])

    def test_ambiguous_or_mismatched_alignment_is_omitted(self):
        self.assertEqual(reading_spans('取あ扱', 'とああつか'), [])
        self.assertEqual(reading_spans('食べる', 'しょく'), [])
        self.assertEqual(reading_spans('かな', 'カナ'), [])

    def test_symbol_union_and_missing_geometry(self):
        region = line_region('今日は')
        self.assertEqual(span_rect(region, 0, 2), {'left': 10, 'top': 50, 'right': 50, 'bottom': 75})
        region['symbols'].pop(1)
        self.assertIsNone(span_rect(region, 0, 2))

    def test_vertical_and_zero_size_boxes_are_not_used(self):
        region = line_region('食')
        region['horizontal'] = False
        self.assertIsNone(span_rect(region, 0, 1))
        region['horizontal'] = True
        region['symbols'][0]['rect']['right'] = 10
        self.assertIsNone(span_rect(region, 0, 1))

    def test_offsets_are_codepoints_not_utf16_units(self):
        region = line_region('😀食べる')
        self.assertEqual(span_rect(region, 1, 2)['left'], 30)


class ScreenAISchemaTests(unittest.TestCase):
    def annotation(self, text='今日'):
        annotation = proto.VisualAnnotation()
        line = annotation.lines.add(utf8_string=text, confidence=.9, direction=1)
        line.bounding_box.CopyFrom(proto.Rect(x=10, y=50, width=40, height=25))
        word = line.words.add(utf8_string=text)
        for i, char in enumerate(text):
            symbol = word.symbols.add(utf8_string=char)
            symbol.bounding_box.CopyFrom(proto.Rect(x=10 + 20 * i, y=50, width=20, height=25))
        return annotation

    def test_symbol_offsets_survive_scaled_ocr_serialization(self):
        output = _proto_to_regions(self.annotation().SerializeToString(), 2, 2, .5)[0]
        self.assertEqual(output['symbols'][1]['start'], 1)
        self.assertEqual(output['symbols'][1]['rect']['left'], 60)
        region = TextRegion(output['text'], output['rect'], symbols=output['symbols'], horizontal=output['horizontal'])
        self.assertEqual(region.to_dict()['symbols'], output['symbols'])

    def test_mismatched_symbols_are_not_guessed(self):
        annotation = self.annotation()
        annotation.lines[0].words[0].symbols[0].utf8_string = '違'
        self.assertEqual(_proto_to_regions(annotation.SerializeToString(), 1, 1, .5)[0]['symbols'], [])

    def test_vertical_line_uses_fallback(self):
        annotation = self.annotation()
        annotation.lines[0].direction = 3
        self.assertFalse(_proto_to_regions(annotation.SerializeToString(), 1, 1, .5)[0]['horizontal'])


class OfflineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = JapaneseReader()

    def test_real_tokenizer_geometry_and_inflected_dictionary_lookup_offline(self):
        with patch('socket.socket.connect', side_effect=AssertionError('Network must not be used')):
            result = self.reader.analyze([line_region('食べました。')])
            word = next(t for t in result[0]['learningTokens'] if t['lemma'] == '食べる')
            self.assertEqual(word['reading'], 'たべ')
            self.assertEqual(word['ruby'][0]['reading'], 'た')
            self.assertEqual(word['ruby'][0]['rect']['right'], 30)
            entries = self.reader.lookup(word['surface'], word['lemma'], word['reading'])
            self.assertTrue(any('to eat' in s['glosses'] for e in entries for s in e['senses']))

    def test_single_kanji_and_line_only_fallback(self):
        region = line_region('猫')
        del region['symbols']
        token = self.reader.analyze([region])[0]['learningTokens'][0]
        self.assertEqual(token['reading'], 'ねこ')
        self.assertIsNone(token['rect'])

    def test_unknown_and_wildcard_queries_do_not_expand_dictionary(self):
        self.assertEqual(self.reader.lookup('ほげほげ未知語', 'ほげほげ未知語', ''), [])
        self.assertEqual(self.reader.lookup('食%', '食%', ''), [])

    def test_non_japanese_regions_are_ignored(self):
        self.assertEqual(self.reader.analyze([line_region('Start game 123')]), [])

    def test_repeated_tokens_keep_distinct_positions(self):
        tokens = self.reader.analyze([line_region('猫と猫')])[0]['learningTokens']
        cats = [t for t in tokens if t['surface'] == '猫']
        self.assertEqual(len(cats), 2)
        self.assertNotEqual(cats[0]['id'], cats[1]['id'])
        self.assertNotEqual(cats[0]['rect'], cats[1]['rect'])

    def test_real_worker_reuse_serialization_and_shutdown(self):
        service = JapaneseService(str(ROOT))
        try:
            result = service.request('analyze', regions=[line_region('猫')])
            self.assertEqual(result[0]['learningTokens'][0]['reading'], 'ねこ')
            pid = service.process.pid
            with ThreadPoolExecutor(max_workers=3) as pool:
                entries = list(pool.map(lambda _: service.request('lookup', surface='猫', lemma='猫', reading='ねこ'), range(3)))
            self.assertTrue(all(entries))
            self.assertEqual(service.process.pid, pid)
            process = service.process
        finally:
            service.close()
        self.assertIsNotNone(process.poll())

    def test_failed_worker_request_can_restart(self):
        service = JapaneseService(str(ROOT))
        try:
            with self.assertRaises(RuntimeError):
                service.request('unknown')
            self.assertIsNone(service.process)
            self.assertTrue(service.request('lookup', surface='猫', lemma='猫', reading='ねこ'))
        finally:
            service.close()

    def test_worker_timeout_terminates_process(self):
        service = JapaneseService(str(ROOT))
        try:
            with patch('providers.japanese_service.select.select', return_value=([], [], [])):
                with self.assertRaises(TimeoutError):
                    service.request('analyze', regions=[])
            self.assertIsNone(service.process)
        finally:
            service.close()


# Exercise the real RPC methods without importing the Steam/Decky host runtime.
def rpc_plugin():
    tree = ast.parse((ROOT / 'main.py').read_text())
    plugin = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Plugin')
    methods = [n for n in plugin.body if getattr(n, 'name', '') in ('read_japanese_file', 'discard_screenshot', 'lookup_japanese')]
    scope = {'Path': Path, 'asyncio': asyncio, 'ProviderType': ProviderType,
             'logger': __import__('logging').getLogger('rpc-test')}
    exec(compile(ast.Module(body=methods, type_ignores=[]), 'main.py', 'exec'), scope)
    return type('RPCPlugin', (), {n.name: scope[n.name] for n in methods})()


class RPCTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_outside_screenshot_without_deleting(self):
        plugin = rpc_plugin()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'outside.png'
            path.write_bytes(b'unchanged')
            plugin._screenshotPath = str(Path(root) / 'captures')
            result = await plugin.read_japanese_file(str(path))
            self.assertIn('error', result)
            await plugin.discard_screenshot(str(path))
            self.assertTrue(path.exists())

    async def test_offline_provider_guard_and_cleanup(self):
        plugin = rpc_plugin()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'capture.png'
            path.write_bytes(b'image')
            plugin._screenshotPath = root
            plugin._ocr_provider = 'gemini_vision'
            result = await plugin.read_japanese_file(str(path))
            self.assertIn('Chrome Screen AI', result['message'])
            self.assertFalse(path.exists())

    async def test_ocr_does_not_block_event_loop_and_analyzes_raw_regions(self):
        plugin = rpc_plugin()
        class Provider:
            def is_available(self, language):
                return language == 'ja'

            async def recognize(self, data, language):
                time.sleep(.08)  # Real providers use blocking pipe reads.
                return [TextRegion('猫', line_region('猫')['rect'])]

        class Manager:
            def get_ocr_provider(self, kind):
                return Provider()

        class Service:
            def request(self, action, **values):
                return values['regions']

        plugin._provider_manager = Manager()
        plugin._get_japanese_service = lambda: Service()
        plugin._ocr_provider = 'chromescreenai'
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'capture.png'
            path.write_bytes(b'image')
            plugin._screenshotPath = root
            task = asyncio.create_task(plugin.read_japanese_file(str(path)))
            await asyncio.sleep(.02)
            self.assertFalse(task.done())
            result = await task
            self.assertEqual(result[0]['text'], '猫')
            self.assertFalse(path.exists())
            self.assertFalse(plugin._reading_busy)


if __name__ == '__main__':
    unittest.main()
