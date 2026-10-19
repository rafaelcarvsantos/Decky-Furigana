"""Offline Japanese analysis. Loaded only inside the Python 3.13 worker."""
import functools
import re

KANJI = re.compile(r"[\u3400-\u9fff\uf900-\ufaff々〆ヵヶ]+")


def hiragana(value):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in value)


def reading_spans(surface, reading):
    """Align kana anchors to a reading; refuse ambiguous okurigana splits."""
    chunks = [(m.start(), m.end(), m.group()) for m in
              re.finditer(r"[\u3400-\u9fff\uf900-\ufaff々〆ヵヶ]+|[^\u3400-\u9fff\uf900-\ufaff々〆ヵヶ]+", surface)]
    reading = hiragana(reading)
    if not reading or not KANJI.search(surface) or len(surface) > 100 or len(reading) > 200:
        return []

    @functools.lru_cache(maxsize=None)
    def visit(index, offset):
        if index == len(chunks):
            return [()] if offset == len(reading) else []
        start, end, text = chunks[index]
        results = []
        if KANJI.fullmatch(text):
            for stop in range(offset + 1, len(reading) + 1):
                for suffix in visit(index + 1, stop):
                    results.append(((start, end, reading[offset:stop]),) + suffix)
                    if len(results) == 2:
                        return results
        else:
            kana = hiragana(text)
            if reading.startswith(kana, offset):
                return visit(index + 1, offset + len(kana))
        return results

    solutions = visit(0, 0)
    return [{"start": s, "end": e, "reading": r} for s, e, r in solutions[0]] if len(solutions) == 1 else []


def span_rect(region, start, end):
    if not region.get("horizontal", True):
        return None
    symbols = [s for s in region.get("symbols", []) if s["start"] >= start and s["end"] <= end]
    cursor = start
    for symbol in symbols:
        if symbol["start"] != cursor:
            return None
        cursor = symbol["end"]
    if not symbols or cursor != end:
        return None
    rects = [s["rect"] for s in symbols]
    if any(r["right"] <= r["left"] or r["bottom"] <= r["top"] for r in rects):
        return None
    return {"left": min(r["left"] for r in rects), "top": min(r["top"] for r in rects),
            "right": max(r["right"] for r in rects), "bottom": max(r["bottom"] for r in rects)}


def learner_groups(text, tokens):
    """Conservative, contiguous morphology grouping; never cross OCR gaps."""
    groups = []
    index = 0

    def match(start, surfaces, positions):
        pieces = tokens[start:start + len(surfaces)]
        return (len(pieces) == len(surfaces)
                and all(t['surface'] == surface and t['pos'] == pos
                        for t, surface, pos in zip(pieces, surfaces, positions))
                and all(a['end'] == b['start'] for a, b in zip(pieces, pieces[1:])))

    while index < len(tokens):
        head = tokens[index]
        end = index + 1
        grammar = []
        kind = 'vocabulary'
        # UniDic may split かも into two particles. Reject lexical 鴨/知れない.
        if match(index, ('か', 'も', 'しれ', 'ない'), ('助詞', '助詞', '動詞', '助動詞')):
            end = index + 4
            kind = 'grammar'
            grammar.append({'pattern': 'かもしれない', 'meaning': 'May / might; expresses possibility.'})
        elif (match(index, ('じゃ', 'ない', 'か'), ('助動詞', '形容詞', '助詞'))
              and tokens[index + 2]['pos2'] == '終助詞'
              and re.fullmatch(r'[\s。！？!?…」』）)よね]*', text[tokens[index + 2]['end']:])):
            end = index + 3
            kind = 'grammar'
            grammar.append({'pattern': 'じゃないか', 'meaning':
                            'Sentence ending: may seek agreement, emphasize a reaction, or express realization. '
                            'A literal negative question is also possible; context determines the meaning.'})
        elif head['pos'] in ('動詞', '形容詞'):
            while end < len(tokens) and tokens[end - 1]['end'] == tokens[end]['start']:
                previous, following = tokens[end - 1], tokens[end]
                # Negative conditional + ばならない is an obligation construction.
                if (head['pos'] == '動詞' and previous['cform'].startswith('未然形')
                        and match(end, ('なけれ', 'ば', 'なら', 'ない'),
                                  ('助動詞', '助詞', '動詞', '助動詞'))):
                    end += 4
                    grammar.append({'pattern': '〜なければならない', 'meaning': 'Must / have to; expresses obligation.'})
                    break
                # Connective て/で is included only with kana auxiliary いる.
                if (previous['cform'].startswith('連用形')
                        and following['surface'] in ('て', 'で') and following['pos2'] == '接続助詞'
                        and end + 1 < len(tokens)
                        and following['end'] == tokens[end + 1]['start']
                        and tokens[end + 1]['pos'] == '動詞'
                        and tokens[end + 1]['pos2'] == '非自立可能'
                        and tokens[end + 1]['lemma'] == '居る'
                        and re.fullmatch('[いれろるよ]+', tokens[end + 1]['surface'])):
                    end += 2
                    grammar.append({'pattern': '〜ている', 'meaning':
                                    'Progressive or continuing state; 〜ていた is the past form. '
                                    'The interpretation depends on the verb and context.'})
                    continue
                # Inflectional auxiliaries attach to an inflecting preceding form.
                if (previous['cform'].startswith(('未然形', '連用形'))
                        and following['pos'] == '助動詞'
                        and following['ctype'] in ('助動詞-タ', '助動詞-ナイ', '助動詞-タイ',
                                                   '助動詞-マス', '助動詞-レル', '助動詞-ラレル',
                                                   '助動詞-セル', '助動詞-サセル')):
                    end += 1
                    if following['ctype'] == '助動詞-タイ':
                        grammar.append({'pattern': '〜たい', 'meaning': 'Want to do; expresses desire.'})
                    continue
                if (head['pos'] == '形容詞' and previous['cform'].startswith('連用形')
                        and following['pos'] == '形容詞' and following['lemma'] == '無い'):
                    end += 1
                    continue
                break
            if end > index + 1:
                kind = 'inflected'

        pieces = tokens[index:end]
        unit = dict(head)
        unit.update(surface=text[head['start']:pieces[-1]['end']], end=pieces[-1]['end'],
                    reading=''.join(t['reading'] for t in pieces) if all(t['reading'] for t in pieces) else '',
                    morphology=[dict(t) for t in pieces], kind=kind, grammar=grammar)
        # Keep per-morpheme alignment instead of guessing a reading for the whole group.
        unit['ruby'] = [dict(span, start=span['start'] + t['start'] - head['start'],
                             end=span['end'] + t['start'] - head['start'])
                        for t in pieces for span in t['ruby']]
        if kind == 'grammar':
            unit['lemma'] = unit['surface']
        groups.append(unit)
        index = end
    return groups


class JapaneseReader:
    def __init__(self):
        import fugashi
        import unidic_lite
        from jamdict import Jamdict
        self.tagger = fugashi.Tagger('-d "' + unidic_lite.DICDIR + '"')
        self.dictionary = Jamdict()

    @functools.lru_cache(maxsize=512)
    def tokenize(self, text):
        tokens = []
        cursor = 0
        for word in self.tagger(text):
            start = text.find(word.surface, cursor)
            if start < 0:
                continue
            cursor = start + len(word.surface)
            if word.feature.pos1 in ("補助記号", "記号", "空白"):
                continue
            kana = word.feature.kana if word.feature.kana not in (None, '*') else ''
            lemma = word.feature.lemma if word.feature.lemma not in (None, '*', '') else word.surface
            tokens.append({"surface": word.surface, "lemma": lemma,
                           "reading": hiragana(kana), "pos": word.feature.pos1,
                           "start": start, "end": cursor,
                           "ruby": reading_spans(word.surface, kana),
                           "pos2": word.feature.pos2, "ctype": word.feature.cType,
                           "cform": word.feature.cForm})
        return learner_groups(text, tokens)

    def analyze(self, regions):
        results = []
        for line_index, region in enumerate(regions[:150]):
            if not re.search(r'[\u3040-\u30ff\u3400-\u9fff]', region.get("text", "")):
                continue
            if len(region.get("text", "")) > 2000:
                continue
            tokens = []
            for index, original in enumerate(self.tokenize(region["text"])):
                token = dict(original, id=f"{line_index}:{index}", rect=span_rect(region, original["start"], original["end"]))
                token["ruby"] = [dict(span, rect=span_rect(region, original["start"] + span["start"],
                                                          original["start"] + span["end"])) for span in original["ruby"]]
                tokens.append(token)
            if tokens:
                results.append(dict(region, translatedText="", learningTokens=tokens))
        return results

    @functools.lru_cache(maxsize=512)
    def lookup(self, surface, lemma, reading):
        entries = []
        seen = set()
        # UniDic lemmas can carry pronunciation suffixes, e.g. アイス-ice.
        for term in dict.fromkeys((surface, lemma.split("-", 1)[0])):
            if not term or len(term) > 100 or any(c in term for c in '%?_'):
                continue
            result = self.dictionary.lookup(term, lookup_ne=False, lookup_chars=False)
            for entry in result.entries:
                data = entry.to_dict()
                if data["idseq"] in seen:
                    continue
                seen.add(data["idseq"])
                senses = []
                for sense in data.get("senses", []):
                    glosses = [g["text"] for g in sense.get("SenseGloss", []) if g.get("lang", "eng") == "eng"]
                    if glosses:
                        senses.append({"glosses": glosses, "pos": sense.get("pos", [])})
                if senses:
                    entries.append({"id": str(data["idseq"]), "spellings": [k["text"] for k in data.get("kanji", [])],
                                    "readings": [k["text"] for k in data.get("kana", [])], "senses": senses[:5]})
        entries.sort(key=lambda e: reading not in e["readings"])
        return entries[:8]
