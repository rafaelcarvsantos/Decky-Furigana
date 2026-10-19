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
createRoot(document.getElementById('root')).render(
    <JapaneseAnnotations regions={regions} width={640} height={400} scaleX={0.5} scaleY={0.5}
        onDismiss={() => { window.readerDismissed = true; }} />);
