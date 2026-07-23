# Spotify Card Source Management Implementation Plan

**Status:** In progress (Phases 1–2 complete)

**Goal:** Make Spotify sources easy to add, understand, find, test, and update
from the Cards web UI without requiring users to manually manage Spotify URIs.

**Current state:** Spotify card playback is already supported through the
`play_spotify` command alias. The Cards form accepts only a raw Spotify URI,
the Cards overview displays that raw command data, and there is no Spotify
search or source preview.

**Architecture:** Keep the existing `cards.yaml` representation and
`play_spotify` playback path. Add card-oriented Spotify RPC methods for source
normalization, metadata resolution, and search. Use those methods in the
existing Cards workflow so stored mappings remain portable and backward
compatible.

**Tech Stack:** Python 3, Spotipy, pytest, React 17, Material UI, Jest/Testing
Library, i18next.

---

## Progress

- [x] Phase 1: Normalize and resolve Spotify sources
- [x] Phase 2: Improve the Spotify card editor
- [ ] Phase 3: Improve the Cards overview
- [ ] Phase 4: Add Spotify search and selection
- [ ] Phase 5: Add optional personal-library browsing
- [ ] Complete local verification
- [ ] Complete Raspberry Pi deployment and end-to-end verification

## Product decisions

- Continue storing only the canonical Spotify URI in the card mapping.
- Preserve existing `play_spotify` card entries without migration.
- Support tracks, albums, and playlists initially.
- Accept both `open.spotify.com` share URLs and `spotify:` URIs.
- Resolve names, artwork, artists, and owners from Spotify instead of
  duplicating mutable metadata in `cards.yaml`.
- Deliver search before personal-library browsing so the initial feature does
  not require broader OAuth scopes.

## Out of scope for the initial release

- Editing Spotify playlists or saved-library contents.
- Persisting Spotify artwork or descriptive metadata in card mappings.
- Supporting episodes, shows, artists, or other URI types before their playback
  behavior is explicitly defined and tested.
- Changing the Spotify playback architecture or player arbiter.

---

### Task 1: Source parsing, normalization, and validation

**Files:**

- Modify: `src/jukebox/components/playerspotify/__init__.py`
- Create or modify: `test/playerspotify/test_player.py`
- Modify: `src/webapp/src/commands/index.js`

- [x] Define a single normalized source response containing canonical URI,
  external URL, type, name, subtitle, and image URL.
- [x] Add a pure helper that recognizes supported Spotify URIs and share URLs.
- [x] Strip irrelevant URL query parameters and reject malformed or unsupported
  source types.
- [x] Add a tagged `resolve_source(value)` RPC method that fetches the matching
  Spotify object and returns normalized metadata.
- [x] Return distinguishable errors for invalid input, unavailable
  authentication, missing Spotify content, and transient API failures.
- [x] Register the RPC method in the webapp command map.
- [x] Add unit tests for valid track, album, and playlist URIs and URLs.
- [x] Add unit tests for malformed input, unsupported types, missing metadata,
  missing artwork, and Spotify API errors.

**Acceptance criteria:**

- Both supported URI formats resolve to the same canonical URI.
- Invalid or unsupported input cannot be mistaken for a playable source.
- No credentials, tokens, or authorization details are exposed in RPC results
  or logs.

### Task 2: Spotify card editor preview and validation

**Files:**

- Modify: `src/webapp/src/components/Cards/controls/actions/spotify/index.js`
- Modify: `src/webapp/src/components/Cards/controls/actions-controls.js`
- Modify: `src/webapp/public/locales/en/translation.json`
- Modify: `src/webapp/public/locales/de/translation.json`
- Create: focused React tests beside the Spotify card controls

- [x] Replace the URI-only wording with a field that accepts a Spotify link or
  URI.
- [x] Resolve input after a short debounce or an explicit preview action,
  avoiding an API call on every keystroke.
- [x] Show loading, resolved, invalid, unavailable, and retry states.
- [x] Display artwork, source type, name, and artist or owner when resolution
  succeeds.
- [x] Save the canonical URI returned by the backend.
- [x] Disable Save while the Spotify source is empty, unresolved, invalid, or
  still loading.
- [x] Preserve the user's input when resolution fails.
- [x] Add an “Open in Spotify” action for a resolved source.
- [x] Add a “Test playback” action with clear success/error feedback.
- [x] Ensure existing URI-based card mappings load and resolve in the editor.
- [x] Add English and German translations.
- [x] Add React tests for paste, loading, successful preview, validation
  failures, retry, canonical save, and existing mappings.

**Acceptance criteria:**

- A user can paste the link produced by Spotify's normal Share action.
- The user can verify what a card will play before saving it.
- Existing Spotify cards remain editable without manual conversion.

### Task 3: Human-readable Spotify cards overview

**Files:**

- Modify: `src/jukebox/components/playerspotify/__init__.py`
- Modify: `src/webapp/src/commands/index.js`
- Modify: `src/webapp/src/components/Cards/overview.js`
- Modify: `src/webapp/src/components/Cards/list.js`
- Create or modify: focused backend and React tests

- [ ] Add a batch `resolve_sources(uris)` RPC method, or an equivalent bounded
  resolver, to avoid one browser request per card.
- [ ] Deduplicate repeated URIs within a batch.
- [ ] Bound Spotify request concurrency and handle partial failures.
- [ ] Add an in-memory metadata cache with a documented expiration policy.
- [ ] Identify Spotify cards from their decoded `play_spotify` alias/action.
- [ ] Display source name, type, artist or owner, Spotify icon, and optional
  artwork instead of the raw command.
- [ ] Fall back to the canonical URI if Spotify is disconnected or metadata
  cannot be resolved.
- [ ] Add text search across card ID, source name, and subtitle.
- [ ] Add filters for Spotify, local music, and control cards.
- [ ] Keep list rendering useful while metadata loads incrementally.
- [ ] Test empty lists, mixed card types, duplicate Spotify sources, partial
  failures, filtering, and fallback display.

**Acceptance criteria:**

- The overview remains responsive with multiple Spotify cards.
- One unresolved Spotify item does not prevent other cards from displaying.
- Users can locate a card by either RFID number or recognizable source name.

### Task 4: Spotify search and source picker

**Files:**

- Modify: `src/jukebox/components/playerspotify/__init__.py`
- Modify: `src/webapp/src/commands/index.js`
- Create: Spotify picker components under
  `src/webapp/src/components/Cards/controls/actions/spotify/`
- Modify: Spotify card editor and translations
- Create or modify: focused backend and React tests

- [ ] Add a tagged `search_sources(query, types, limit, offset)` RPC method.
- [ ] Restrict types, limits, and offsets to safe server-side values.
- [ ] Normalize track, album, and playlist search results to the same source
  shape used by `resolve_source`.
- [ ] Add a “Choose from Spotify” action beside the paste field.
- [ ] Provide a debounced search field and track/album/playlist filters.
- [ ] Show result artwork, name, subtitle, and type.
- [ ] Add pagination or incremental loading.
- [ ] Return the selected source to the existing Cards form and preview.
- [ ] Provide accessible loading, empty, error, and keyboard-selection states.
- [ ] Test query validation, result normalization, pagination, stale response
  handling, selection, and cancellation.

**Acceptance criteria:**

- A user can assign a Spotify source without leaving the jukebox web UI.
- Selecting a search result uses the same validation and storage path as pasted
  input.

### Task 5: Optional personal Spotify library

**Dependency:** Complete only after Tasks 1–4 have been evaluated in normal use.

- [ ] Decide which personal views are valuable: playlists, saved albums,
  recently played, or recently assigned.
- [ ] Document the additional OAuth scopes required for each chosen view.
- [ ] Design a safe reauthorization flow for already-connected installations.
- [ ] Add backend pagination and normalized results for approved views.
- [ ] Reuse the Spotify picker UI for browsing and selection.
- [ ] Explain private-content permissions before requesting reconnection.
- [ ] Test scope upgrades, declined consent, revoked access, pagination, and
  empty libraries.

**Acceptance criteria:**

- Existing playback-only users are not forced to grant broader permissions
  unless they opt into personal-library features.

### Task 6: Local integration verification

- [ ] Run focused Spotify backend tests.
- [ ] Run RFID cards and RPC-related backend tests.
- [ ] Run focused Cards/Spotify React tests.
- [ ] Run the complete relevant webapp test suite.
- [ ] Run the production webapp build.
- [ ] Verify that existing cards require no data migration.
- [ ] Review RPC payloads and logs for token or credential disclosure.
- [ ] Exercise rate-limit, disconnected, timeout, and partial-failure behavior.
- [ ] Record commands, results, and any unrelated pre-existing failures.

### Task 7: Raspberry Pi deployment and end-to-end verification

- [ ] Follow the established Pi preflight and backup process before deployment.
- [ ] Deploy the complete tested backend and webapp revision together.
- [ ] Verify Spotify authentication and selected Connect device without
  exposing secrets.
- [ ] Register a card using a pasted Spotify share URL.
- [ ] Register another card using Spotify search.
- [ ] Edit an existing URI-based Spotify card.
- [ ] Verify overview metadata, search, filters, fallback behavior, and artwork.
- [ ] Swipe track, album, and playlist cards and confirm playback.
- [ ] Verify Spotify-to-MPD and MPD-to-Spotify switching remains correct.
- [ ] Restart services and confirm mappings and behavior persist.
- [ ] Update this document's status and checkboxes with verified results.

---

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Spotify rate limits | Debounce search, batch resolution, cache metadata, and honor retryable errors. |
| Stale browser requests | Cancel or ignore responses that no longer match the current input/query. |
| OAuth scope expansion | Keep initial search within current permissions and isolate personal-library work. |
| Metadata unavailable | Store only the canonical URI and retain a raw-URI fallback in the UI. |
| Existing cards regress | Preserve `play_spotify` and add explicit compatibility tests using current mappings. |
| Large card collections load slowly | Deduplicate URIs, resolve in bounded batches, cache, and render incrementally. |

## Completion record

Update this section as work progresses.

- **Implementation started:** 2026-07-23
- **Implementation completed:** Not completed
- **Deployed revision:** Not deployed
- **Verification summary:** Phase 1 focused cases passed via a lightweight local
  runner; Python/JavaScript syntax and diff checks passed. Phase 2's focused and
  complete React test suites pass (12 tests), and the production webapp build
  succeeds with only unrelated pre-existing hook warnings. The standard pytest
  runner remains unavailable because this checkout has no `.venv` and system
  Python does not have pytest installed.
- **Known follow-ups:** None recorded
