import { call } from '@decky/api';
import type { TranslatedRegion } from './TextTranslator';

export interface ReadingRect { left: number; top: number; right: number; bottom: number }
export interface ReadingToken {
    id: string;
    surface: string;
    lemma: string;
    reading: string;
    pos: string;
    kind?: "vocabulary" | "inflected" | "grammar";
    grammar?: Array<{ pattern: string; meaning: string }>;
    morphology?: Array<{ surface: string; lemma: string; reading: string; pos: string;
        pos2: string; ctype: string; cform: string; start: number; end: number }>;
    rect: ReadingRect | null;
    ruby: Array<{ reading: string; rect: ReadingRect | null }>;
}
export interface DictionaryEntry {
    id: string;
    spellings: string[];
    readings: string[];
    senses: Array<{ glosses: string[]; pos: string[] }>;
}

export async function readJapanese(path: string): Promise<TranslatedRegion[]> {
    const response = await call<[string], TranslatedRegion[] | { error: string; message: string }>('read_japanese_file', path);
    if (!Array.isArray(response)) throw new Error(response?.message || 'Japanese reading failed');
    return response;
}

export async function lookupJapanese(token: ReadingToken): Promise<DictionaryEntry[]> {
    if (token.kind === "grammar") return [];
    const response = await call<[string, string, string], DictionaryEntry[] | { error: string; message: string }>(
        'lookup_japanese', token.surface, token.lemma, token.reading);
    if (!Array.isArray(response)) throw new Error(response?.message || 'Dictionary lookup failed');
    return response;
}
