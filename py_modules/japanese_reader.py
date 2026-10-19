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
                           "ruby": reading_spans(word.surface, kana)})
        return tokens

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
