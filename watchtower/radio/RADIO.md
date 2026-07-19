# Deck radio — music sourcing + OC ReMix compliance

The deck radio (`deck/deck-radio.js`) is manifest-driven ambiance. It is
**user-initiated only** (no autoplay), **never behind a fee**, and the
player is branded "deck radio" — never "OC ReMix radio" (no implied
endorsement).

## Using OC ReMix tracks (their Terms of Use, summarized 2026-07)

OCR permits using their content in streams/venues **as long as you're not
profiting directly from its usage**, with credit to **ocremix.org AND the
artist(s)**, and shared files must keep **original names + tags**. They
reserve the right to terminate the license at any time.

Our compliance rules — enforced by how the player is built:

1. **Ambiance, not product.** The music is free background on free pages.
   No track ever sits behind a payment, a tier, or a paywalled surface, and
   nothing scry sells is "the music." (Selling reads/labor alongside free
   ambient music = the "store with music on" case their terms allow.)
2. **Credit is rendered, always.** Every `files` track entry REQUIRES
   `title`, `artist`, `url` (its ocremix.org track page); the now-playing
   bar renders "title — artist · track · ocremix.org" with live links.
   A track without credit fields doesn't play.
3. **Files keep their identity.** Deploy MP3s to the VM under
   `watchtower/radio/tracks/` with **original filenames and tags intact**
   (git-ignored — audio never enters the repo).
4. **Removable in one edit.** If OCR ever objects, empty the manifest —
   the license-termination clause is why the whole layer is swappable.
   Fallbacks: CC-BY chiptune, or commissioned original loops.

## Stream stations (e.g. Rainwave's OCR channel)

`{"type":"stream","src":"<url>","name":"...","info":"<their page>"}` —
before enabling one: verify the relay URL is meant for public embedding,
and add its host to the nginx CSP `media-src` (backend follow-up; the
static site itself stays CSP-clean).

## Manifest shape

```json
{ "stations": [
  { "id": "omen", "name": "the omen rotation", "type": "files",
    "tracks": [ { "src": "/radio/tracks/<original-name>.mp3",
                  "title": "…", "artist": "…",
                  "url": "https://ocremix.org/remix/OCR0XXXX" } ] },
  { "id": "rw", "name": "rainwave · ocr", "type": "stream",
    "src": "…", "info": "https://rainwave.cc" } ] }
```
