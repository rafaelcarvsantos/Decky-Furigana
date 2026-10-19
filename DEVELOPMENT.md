# Japanese reading mode

The first implementation reads a captured game frame, adds furigana above
recognized kanji where OCR symbol boxes are available, and opens English
dictionary senses when a word is selected. It uses no Furifont, cloud translation,
or language model. The existing translation mode remains available.

## Install this fork on Steam Deck

The fork keeps the `Decky Translator` display name and `decky-translator` folder
for compatibility. It replaces the upstream plugin; do not install both together.
Do not use the upstream store/release package for Japanese mode.

### From new GitHub Actions builds (preferred)

Run **Build and Release** using workflow_dispatch on the desired branch, or use a
main/PR build. Download the `decky-translator-plugin` artifact, extract the Actions
wrapper ZIP, and install the inner **Decky-Furigana-Install.zip** through Decky
Settings → General → Developer Mode → Developer → Install Plugin from ZIP.
Do not select the Actions wrapper ZIP. The inner ZIP is self-contained; the
separate dependency artifact is only needed for repacking older builds.

### Repair the already downloaded artifacts without building Python or Node

Use the inner `Decky Translator.zip` and `plugin-dependencies.tar.gz` from the
**same workflow run**, not their outer Actions wrapper ZIPs. With the files already
at the locations used on this Deck:

```sh
cd /home/deck/Projects/Decky-Furigana
python3 scripts/package_install.py \
  '/home/deck/decky-furigana-build/Decky Translator.zip' \
  /home/deck/decky-furigana-build/plugin-dependencies.tar.gz \
  /home/deck/Projects/Decky-Furigana/out/Decky-Furigana-Install.zip
```

Install `out/Decky-Furigana-Install.zip` through Developer Mode. The script verifies
the old artifact's dependency SHA256, removes `remote_binary` from the packaged
manifest, repairs the old startup directory check, and stores the compressed
archive at `decky-translator/bin/plugin-dependencies.tar.gz`. It does not alter
input files, installed plugins, SteamOS, settings, or saves.

### Why the old installation failed

Decky Loader reads `package.json` after unzipping and downloads **every** declared
`remote_binary`; already bundled files do not skip that step. The old workflow
changed the tag/hash but retained `cat-in-a-box/Decky-Translator` in the URL. Dev
builds did not publish any corresponding release, either. Changing only the URL
would still leave a missing dev release or an unpublished draft release.
Failed remote downloads leave extracted files behind but skip plugin import.
See [Decky's installer implementation](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/browser.py).

The new installer declares no remote binaries. First startup extracts the tarball
under `bin/`, preserving executable bits and symlinks that ZIP extraction alone
would lose. Expected paths:

```text
decky-translator/
  plugin.json
  package.json                 # no remote_binary
  main.py
  dist/index.js
  py_modules/                  # plugin source, providers and worker
  bin/plugin-dependencies.tar.gz
  bin/py_modules/               # extracted pip packages and dictionaries
  bin/python313/python/bin/python3.13
  bin/.dependencies-extracted
```

Keep roughly 2 GiB free for the installer, archive and extracted data. First load
can take longer while unpacking. Subsequent loads reuse the extracted files.
The startup check now looks for `bin/py_modules/rapidocr`, matching the archive,
rather than the nonexistent `bin/rapidocr` which caused repeated extraction.
Decky assigns ownership for its host user and the plugin extracts as that user;
no `chmod 777`, system Python installation or SteamOS read-only changes are needed.

### Troubleshooting and runtime check

After an installation failure, restart Decky once before retrying: older loader
versions can leave their plugin watcher disabled on this error path. This briefly
interrupts all Decky plugins; it does not delete their data:

```sh
sudo systemctl restart plugin_loader.service
journalctl -u plugin_loader.service -n 150 --no-pager
```

The display name remains **Decky Translator**. If logs still mention downloading
remote binaries, the selected ZIP is stale or a second folder with the same
`plugin.json` name exists. Inspect rather than deleting directories blindly:

```sh
find /home/deck/homebrew/plugins -maxdepth 2 -name plugin.json -print
cat /home/deck/homebrew/plugins/decky-translator/package.json
ls -ld /home/deck/homebrew/plugins/decky-translator/bin
```

Once startup completes, verify the portable runtime and actual offline data as
the normal `deck` user (no sudo):

```sh
PLUGIN=/home/deck/homebrew/plugins/decky-translator
PYTHONPATH="$PLUGIN/bin/py_modules:$PLUGIN/py_modules" \
  "$PLUGIN/bin/python313/python/bin/python3.13" -B -c \
  'from japanese_reader import JapaneseReader; r=JapaneseReader(); print(r.lookup("食べる", "食べる", "たべる"))'
```

Also check journal output for extraction/import errors, available disk space,
and ownership if this fails. Do not manually unpack dependencies into the root
`py_modules` or place the runtime at root `python313`: workers expect `bin/`.
OCR models remain separate one-time downloads through the plugin; the installer
includes dictionaries and Python packages, not Screen AI/RapidOCR/NLLB models.

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
