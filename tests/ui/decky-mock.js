import React from 'react';

export function Focusable({ onCancel, children, ...props }) {
    return React.createElement('div', { ...props, onKeyDown: e => {
        if (e.key === 'Escape') onCancel?.(e);
    } }, children);
}

export function DialogButton({ children, ...props }) {
    return React.createElement('button', props, children);
}

export async function call(method, surface, lemma, reading) {
    window.readerCalls.push({ method, surface, lemma, reading });
    if (window.readerFailure) return { error: 'reading_error', message: 'Dictionary unavailable' };
    if (surface === '猫') await new Promise(resolve => setTimeout(resolve, 150));
    return [{ id: surface, spellings: [surface], readings: [surface === '猫' ? 'ねこ' : 'いぬ'],
        senses: [{ glosses: [surface === '猫' ? 'cat' : surface === '思っていた' ? 'to think' : 'dog'], pos: ['noun'] }] }];
}
