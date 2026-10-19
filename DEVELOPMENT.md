# Japanese reading mode

The first implementation reads a captured game frame, adds furigana above
recognized kanji where OCR symbol boxes are available, and opens English
dictionary senses when a word is selected. It uses no Furifont, cloud translation,
or language model. The existing translation mode remains available.

## Use on Steam Deck

1. Install a plugin build with the **updated dependency archive**. The existing
   published 0.9.1 archive predates this feature and does not contain the Japanese
   packages. The release workflow builds them from `requirements.txt`; installing
   frontend files alone is insufficient. Missing packages produce an overlay error.
2. In Translation settings, choose Chrome Screen AI (recommended) or RapidOCR,
   and install its local OCR models. Persistent OCR mode reduces repeated startup
   costs but uses memory while enabled.
3. Enable **Japanese reading mode** in the main tab. Press **Read Japanese** or use
   the configured capture shortcut. Input/output translation languages and API
   keys are not required in this mode.
4. Tap a recognized word for its reading, lemma and English senses. The word strip
   and Previous/Next buttons also select words. Use Close meaning to clear the
   definition, or Exit / the configured dismissal shortcut to leave the snapshot.
   Decky focusable controls are used for controller navigation; actual Steam focus
   routing and game input leakage still require testing on a device.

Chrome Screen AI's line, word and symbol output is preserved. Readings and hit
targets use complete symbol coverage; missing or mismatched coverage is never
replaced by equal-width guesses. RapidOCR currently exposes line boxes, so its
words are available in the strip. Rotated/vertical text also uses that fallback.
Crowded or top-clipped furigana is omitted from the image and remains accessible
through the strip. Original game text stays visible in the captured frame.

## Development and checks

Use Node 20, pnpm 9 and Python 3.13, matching the bundled runtime. In this cloud
workspace activate the prepared tools with:

```sh
export PATH=/workspace/.cloud-tools/node_modules/.bin:$PATH
source /workspace/.cloud-tools/venv/bin/activate
cd /workspace/Decky-Furigana
```

For another checkout, create/activate a Python 3.13 virtual environment first.

```sh
pnpm install --frozen-lockfile
python -m pip install -r requirements.txt
pnpm run typecheck
pnpm run build
pnpm run test:python
# Install Playwright's Chromium once, or specify an existing Chromium binary.
pnpm exec playwright install chromium
pnpm test
# Cloud alternative, already verified here:
CHROMIUM_PATH=/usr/bin/chromium pnpm test
```

The Python suite exercises real local morphology and dictionary data, alignment,
Screen AI protobuf serialization, worker reuse and cleanup, and RPC behavior.
Browser tests exercise scaled hit targets, selection, stale lookup responses,
cache reuse and navigation with Decky/API mocks and external requests blocked.
These checks do not establish actual game capture, OCR accuracy, or Steam focus.

## Architecture and resources

- `japanese_reader.py` uses fugashi/UniDic for surface readings and dictionary
  forms. Kana anchors align readings to kanji spans, e.g. 食べる → 食[た]べる.
  Ambiguous alignments are left without inline readings.
- JMdict lookup uses the surface and lemma, ranks matching readings first, and
  returns English senses. It is dictionary lookup, not contextual translation.
- `japanese_worker.py` runs in the same Python 3.13 runtime as native OCR packages,
  isolated from Decky's host Python. It loads lazily, stays alive for subsequent
  requests, and caches tokenization and lookups with bounded LRU caches.
- `JapaneseService` serializes requests, bounds response waiting, and restarts a
  failed worker. The worker closes when reading mode/plugin is disabled or unloaded.
  OCR and analysis run off the backend event loop. Dismissal invalidates results;
  it does not forcibly interrupt native OCR. Another capture waits for cleanup.
- The dictionaries add roughly **560 MiB of uncompressed installed data** with
  these pinned versions. They ship in the dependency archive; no runtime download
  is performed. Do not infer resident memory from database size. Device startup,
  memory, CPU and latency measurements remain outstanding.
- The UI uses installed Japanese font fallbacks. Verify kana coverage offline on
  target SteamOS versions before deciding whether to bundle another font.

## Device acceptance checks still required

- LCD and OLED Deck, Game Mode, offline after initial installation/model download.
- Horizontal dialogue at 1280×800; letterboxed games and external displays.
- Touch selection and controller-only Previous/Next/confirm/back; ensure inputs
  do not activate the underlying game. Check trackpad behavior separately.
- Dismiss during capture/OCR/lookup, recapture after cleanup, suspend/resume,
  plugin disable and unload, and optional pause/resume on failure.
- Compare Chrome Screen AI symbol coverage with actual kanji locations, especially
  repeated characters, punctuation, pre-existing furigana and stylized fonts.
- Measure cold/warm capture-to-readings and lookup p50/p95, memory and CPU on Deck.

Known scope: static snapshots, not tracked annotations over moving gameplay;
horizontal text for inline readings; tokenizer boundaries can split compounds;
rare names, ambiguous readings and OCR mistakes can yield incorrect or missing
readings. The bundled dictionary is a fixed snapshot, not an automatically updated
lexicon. See `THIRD_PARTY_LICENSES` and bundled package/data notices for attribution.
