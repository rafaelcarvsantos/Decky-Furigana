import { DialogButton, Focusable } from '@decky/ui';
import { useEffect, useMemo, useRef, useState, VFC } from 'react';
import { DictionaryEntry, lookupJapanese, ReadingToken } from './JapaneseReader';
import type { TranslatedRegion } from './TextTranslator';

const japaneseFont = '"Noto Sans CJK JP", "Noto Sans JP", "Droid Sans Fallback", sans-serif';

export const JapaneseAnnotations: VFC<{
    regions: TranslatedRegion[]; width: number; height: number;
    scaleX: number; scaleY: number;
    onDismiss: () => void;
}> = ({ regions, width, height, scaleX, scaleY, onDismiss }) => {
    const tokens = useMemo(() => regions.flatMap(r => r.learningTokens || []), [regions]);
    const [selected, setSelected] = useState<ReadingToken | null>(null);
    const [wordsVisible, setWordsVisible] = useState(tokens.some(t => !t.rect));
    const [entries, setEntries] = useState<DictionaryEntry[]>([]);
    const [message, setMessage] = useState('');
    const cache = useRef(new Map<string, DictionaryEntry[]>());

    useEffect(() => {
        let active = true;
        setEntries([]);
        if (!selected) return;
        const key = JSON.stringify([selected.surface, selected.lemma, selected.reading]);
        const cached = cache.current.get(key);
        if (cached) {
            setEntries(cached);
            setMessage(cached.length ? '' : 'No English dictionary entry found.');
            return;
        }
        setMessage('Looking up…');
        lookupJapanese(selected).then(result => {
            cache.current.set(key, result);
            if (!active) return;
            setEntries(result);
            setMessage(result.length ? '' : 'No English dictionary entry found.');
        }).catch(error => {
            if (active) setMessage(error instanceof Error ? error.message : 'Dictionary lookup failed');
        });
        return () => { active = false; };
    }, [selected]);

    // Lay out readings separately from kanji. Crowded annotations remain available
    // in the word strip instead of overlapping their neighbours or moving the text.
    const readings = useMemo(() => {
        const occupied: Array<{ x: number; y: number; w: number; h: number }> = [];
        return tokens.flatMap(token => token.ruby.flatMap((span, index) => {
            if (!span.rect || width <= 0 || height <= 0) return [];
            const rect = span.rect;
            const fontSize = Math.max(11, Math.min(22, (rect.bottom - rect.top) * scaleY * 0.5));
            const w = Math.min(width, Math.max((rect.right - rect.left) * scaleX, span.reading.length * fontSize));
            const h = fontSize * 1.3;
            const x = Math.max(0, Math.min(width - w, (rect.left + rect.right) * scaleX / 2 - w / 2));
            const y = rect.top * scaleY - h - 2;
            if (y < 0 || y + h > height || occupied.some(o => x < o.x + o.w + 2 && x + w + 2 > o.x && y < o.y + o.h && y + h > o.y)) return [];
            occupied.push({ x, y, w, h });
            return [{ key: `${token.id}:${index}`, reading: span.reading, x, y, w, fontSize }];
        }));
    }, [tokens, width, height, scaleX, scaleY]);

    const move = (delta: number) => {
        if (!tokens.length) return;
        const current = selected ? tokens.findIndex(t => t.id === selected.id) : -1;
        setSelected(tokens[current < 0 ? (delta < 0 ? tokens.length - 1 : 0) : (current + delta + tokens.length) % tokens.length]);
    };

    return <>
        {tokens.map(token => token.rect && <button
            key={token.id} aria-label={`${token.surface} ${token.reading}`} title={token.surface}
            onClick={() => setSelected(token)}
            style={{ position: 'absolute', left: token.rect.left * scaleX, top: token.rect.top * scaleY,
                width: (token.rect.right - token.rect.left) * scaleX,
                height: (token.rect.bottom - token.rect.top) * scaleY,
                padding: 0, background: selected?.id === token.id ? 'rgba(68,180,255,.18)' : 'transparent',
                border: selected?.id === token.id ? '2px solid #72cfff' : '1px solid transparent',
                borderRadius: 2, cursor: 'pointer' }} />)}
        {readings.map(label => <span key={label.key} style={{ position: 'absolute', pointerEvents: 'none',
            left: label.x, top: label.y, width: label.w, textAlign: 'center', color: '#fff',
            background: 'rgba(0,0,0,.65)', borderRadius: 3, fontFamily: japaneseFont,
            fontSize: label.fontSize, lineHeight: 1.3, whiteSpace: 'nowrap',
            textShadow: '0 1px 2px #000' }}>{label.reading}</span>)}
        <Focusable onCancel={event => {
            event.preventDefault();
            event.stopPropagation();
            if (selected) setSelected(null);
            else if (wordsVisible) setWordsVisible(false);
            else onDismiss();
        }}
            style={{ position: 'fixed', left: '3vw', right: '3vw', bottom: 16,
                zIndex: 7010, color: '#fff', background: 'rgba(15,20,28,.96)', padding: 12,
                border: '1px solid #5b7185', borderRadius: 8, fontFamily: japaneseFont }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <DialogButton style={{ minWidth: 0, width: 'auto' }} onClick={() => setWordsVisible(v => !v)}>
                    {wordsVisible ? 'Hide words' : 'Words'}
                </DialogButton>
                <DialogButton style={{ minWidth: 0, width: 'auto' }} onClick={() => move(-1)}>Previous</DialogButton>
                <DialogButton style={{ minWidth: 0, width: 'auto' }} onClick={() => move(1)}>Next</DialogButton>
                {selected && <DialogButton style={{ minWidth: 0, width: 'auto' }} onClick={() => setSelected(null)}>Close meaning</DialogButton>}
                <DialogButton style={{ minWidth: 0, width: 'auto' }} onClick={onDismiss}>Exit</DialogButton>
            </div>
            {wordsVisible && <div style={{ maxHeight: '22vh', overflowY: 'auto', marginTop: 8 }}>
                {regions.map((region, i) => <Focusable key={i} style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
                    {region.learningTokens?.map(token => <DialogButton key={token.id}
                        style={{ minWidth: 0, width: 'auto', fontFamily: japaneseFont }} onClick={() => setSelected(token)}>
                        <ruby>{token.surface}<rt>{token.reading}</rt></ruby>
                    </DialogButton>)}
                </Focusable>)}
                <div style={{ fontSize: 12, opacity: .75 }}>Words without exact OCR boxes are shown here. Readings can be ambiguous.</div>
            </div>}
            {selected && <div role="status" aria-live="polite" style={{ maxHeight: '25vh', overflowY: 'auto', marginTop: 8 }}>
                <strong>{selected.surface}</strong>　{selected.reading}　<span style={{ opacity: .7 }}>({selected.lemma})</span>
                {message && <div>{message}</div>}
                {entries.map(entry => <div key={entry.id} style={{ marginTop: 8 }}>
                    <div>{entry.spellings.join('・') || entry.readings.join('・')} — {entry.readings.join('・')}</div>
                    <ol style={{ margin: '4px 0', paddingLeft: 24 }}>{entry.senses.map((sense, i) =>
                        <li key={i}>{sense.glosses.join('; ')}</li>)}</ol>
                </div>)}
                <div style={{ fontSize: 11, opacity: .65 }}>JMdict / EDRDG · Dictionary senses, not a sentence translation</div>
            </div>}
        </Focusable>
    </>;
};
