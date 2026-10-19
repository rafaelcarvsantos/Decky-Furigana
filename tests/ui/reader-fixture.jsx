import React from 'react';
import { createRoot } from 'react-dom/client';
import { JapaneseAnnotations } from '../../src/JapaneseAnnotations';

window.readerCalls = [];
window.readerDismissed = false;
const rect = { left: 100, top: 100, right: 140, bottom: 140 };
const regions = [{ text: '猫と犬', translatedText: '', rect,
    learningTokens: [
        { id: 'cat', surface: '猫', lemma: '猫', reading: 'ねこ', pos: '名詞', rect,
            ruby: [{ reading: 'ねこ', rect }] },
        { id: 'dog', surface: '犬', lemma: '犬', reading: 'いぬ', pos: '名詞', rect: null,
            ruby: [{ reading: 'いぬ', rect: null }] },
    ] }];
const root = createRoot(document.getElementById('root'));
root.render(
    <JapaneseAnnotations regions={regions} width={640} height={400} scaleX={0.5} scaleY={0.5}
        onDismiss={() => { window.readerDismissed = true; }} />);

window.readerShowGroups = () => root.render(
    <JapaneseAnnotations key="grouped" regions={[{ text: '思っていたじゃないか', translatedText: '', rect,
        learningTokens: [
            { id: 'thought', surface: '思っていた', lemma: '思う', reading: 'おもっていた',
                pos: '動詞', kind: 'inflected', rect, ruby: [{ reading: 'おも', rect }],
                grammar: [{ pattern: '〜ている', meaning: 'Continuing state; past 〜ていた.' }] },
            { id: 'ending', surface: 'じゃないか', lemma: 'じゃないか', reading: 'じゃないか',
                pos: '助動詞', kind: 'grammar', rect: null, ruby: [],
                grammar: [{ pattern: 'じゃないか', meaning: 'Sentence ending: agreement or realization; context matters.' }] },
        ] }]} width={640} height={400} scaleX={0.5} scaleY={0.5}
        onDismiss={() => { window.readerDismissed = true; }} />);
