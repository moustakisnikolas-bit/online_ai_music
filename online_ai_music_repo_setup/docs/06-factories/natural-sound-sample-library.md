# Natural Sound Sample Library

## Why sample-based, not synthesized

The original ambient engine only synthesizes sound mathematically (sine
waves, filtered noise). Rain and wind textures in `audio/dsp.py` are
crude approximations of that kind -- filtered noise, not real recordings.
Convincing rain, ocean, forest, fire, and night ambience requires real
recordings layered into a track, not more DSP math.

## Why this can't be auto-populated

Most commercial sound-effect libraries (Soundsnap, Sonniss, Pro Sound
Effects, A Sound Effect) explicitly prohibit exactly this use case in
their license terms: using a sound as the primary content of a product
that gets sold or streamed (their terms call this a "primarily a sound
product," e.g. "soundscape albums," and restrict it directly). This was
confirmed by reading their actual EULAs, not just marketing pages.

The only sourcing path that's safe by construction is **public domain /
CC0-licensed recordings** -- content with no license restrictions at all,
so there's nothing to violate. This requires a human to browse, verify
the license tag, and download real files; it cannot be done by an
automated agent without API credentials for a catalog like Freesound, and
even with those, license verification per file is a judgment call worth
a human doing, not skipping.

## How to add a sample

1. Find a candidate recording. Freesound.org, filtered specifically to
   **CC0** license (not CC-BY, not CC-BY-NC -- CC0 only, since CC-BY
   requires attribution tracking and CC-BY-NC forbids commercial use
   entirely, which this product is).
2. Verify the CC0 tag on the file's own page, not just the search filter
   (filters can be wrong or the uploader can be mistaken).
3. Download the file as WAV. Place it in `apps/api/data/sample_library/` using a
   descriptive filename.
4. Add an entry to `apps/api/data/sample_library/manifest.json`:

   ```json
   {
     "id": "ocean-waves-01",
     "label": "Ocean Waves",
     "category": "ocean",
     "filename": "ocean-waves-01.wav",
     "license": "CC0",
     "source_url": "https://freesound.org/...",
     "attribution": null
   }
   ```

   `source_url` should always be filled in even though CC0 doesn't
   require attribution -- it's the audit trail proving where the file
   came from and that it was actually CC0 at the time of download.

5. Confirm it loads: `GET /api/v1/audio/samples` will show the entry with
   `"available": true` once the file exists on disk; `false` means the
   manifest entry exists but the audio file hasn't been added yet.

## Using a sample in a track

Reference it as a `sample` layer in `mixed_ambient` mode:

```json
{
  "mode": "mixed_ambient",
  "ambient_layers": [
    {"kind": "sample", "sample_id": "ocean-waves-01", "gain": 0.4}
  ]
}
```

The sample is downmixed to mono, resampled to match the request's sample
rate if needed, and looped (simple repeat-and-trim, not a crossfaded
seam) to fill the requested duration. A source recording shorter than the
loop point will produce an audible seam; longer, cleanly-looping source
recordings sound better. Smoothing the loop seam itself (crossfading the
sample's own start/end before tiling) is a known follow-up, not yet
implemented.

## Current state

The five manifest entries in `apps/api/data/sample_library/manifest.json` are
placeholders demonstrating the format (ocean, forest birds, campfire,
thunderstorm, night crickets) -- none of their audio files have been
added yet, so all currently show `"available": false`. Populating them
with real, verified CC0 recordings is a manual step, not done as part of
this milestone.

## AI-generated instrumental clips (Stable Audio Open)

This same library also holds AI-generated instrumental textures ("warm
piano pad," "sustained strings") for Milestone 11 of the production
roadmap. Architecturally these are the same thing as a nature recording
-- a licensed WAV file that gets looped and layered -- so they reuse this
exact manifest and the `sample` ambient layer kind, distinguished by
`"source_type": "ai_generated"` instead of `"recording"`.

Generation goes through [Stable Audio Open](https://stability.ai/news-updates/introducing-stable-audio-open)
via a hosted Replicate API (`stackadoc/stable-audio-open-1.0`), not local
GPU inference -- no GPU management needed, roughly $0.14 per generation.
Chosen after directly verifying license terms on the primary sources
(not aggregator blog posts, which contained real contradictions): the
Stability AI Community License is free for commercial use under $1M/yr
annual revenue, confirmed on Stability AI's own license page. Training an
equivalent model in-house was considered and ruled out -- that's a
different category of undertaking (curated training data at the scale of
~13,000 hours, real ML research expertise, and realistically tens to
hundreds of thousands of dollars in training compute), not something an
incremental build gets you to.

### Setup

Set `REPLICATE_API_TOKEN` in `.env` (get one from
[replicate.com](https://replicate.com)). `STABLE_AUDIO_MODEL` defaults to
`stackadoc/stable-audio-open-1.0` and is configurable if that changes.

### Generating a clip

```
POST /api/v1/audio/samples/generate
{
  "sample_id": "piano-pad-01",
  "label": "Warm Piano Pad",
  "category": "instrumental",
  "prompt": "warm felt piano pad, slow, sustained, calming",
  "duration_seconds": 30
}
```

This calls the model, downloads the result into
`apps/api/data/sample_library/`, and registers a manifest entry
automatically -- no manual file placement needed, unlike CC0 recordings.
Returns `503` if `REPLICATE_API_TOKEN` isn't set.

### Known unknowns (not verifiable without real credentials)

- The exact input parameter names (`prompt`, `seconds_total`, `seed`)
  follow Stable Audio Open's typical inference interface, but
  `stackadoc/stable-audio-open-1.0` is a community-hosted model on
  Replicate, not an "official" model with a schema guarantee --
  verify against the model's actual Replicate page before first real use.
- Whether it actually sounds convincing for the spec's specific
  instrumentation ("warm piano," "sustained strings") is unverified. It's
  built more for texture/sound-design than melodic instruments; quality
  for this specific use case needs a real listening test, not an
  assumption.
- Duration is capped at 30s by default and 47s by the schema, matching
  Stable Audio Open's known output length limit -- generating a full
  20-90 minute track means looping a short clip (the same
  repeat-and-trim mechanism as nature samples), not generating the full
  duration directly.

## Importing CC0 recordings from Freesound

This replaces most of the manual "How to add a sample" workflow above
with a search-and-click flow for real recordings specifically (not
AI-generated clips, which stay on the Stable Audio Open path above).

### Setup

1. Apply for a Freesound API key at
   [freesound.org/apiv2/apply](https://freesound.org/apiv2/apply/).
   Freesound's own docs describe this as an application form, not an
   instant-issue key -- there may be a short approval wait.
2. Once issued, paste the key into Settings -> API Keys -> Freesound API
   Key (or set `FREESOUND_API_KEY` in `.env`). No OAuth setup needed.

### How it works

`POST /api/v1/audio/samples/import-from-freesound` (backed by
`app/services/freesound_importer.py`) fetches Freesound's `preview-hq-ogg`
preview for the chosen sound (not the pristine original -- downloading
that requires Freesound's separate OAuth2 flow, which this integration
deliberately doesn't implement, in exchange for a much simpler "paste a
key" setup), decodes it via `soundfile`, and writes a real 16-bit PCM WAV
into `apps/api/data/sample_library/`, exactly like a manually-added
recording -- `load_sample_layer` doesn't know or care that the file
originated from Freesound rather than a manual download.

License safety is enforced twice: search results are filtered to
`license:"Creative Commons 0"` server-side by Freesound, and the specific
sound's license is re-verified again right before download (in case the
search filter is stale by the time a human picks a result). A non-CC0
sound is refused, not silently imported.

`source_url` is always set to the sound's Freesound page
(`https://freesound.org/s/<id>/`), preserving the same audit-trail
convention as manually-added samples. `source_type` is `"freesound"`,
distinguishing it from a hand-verified `"recording"` or an
`"ai_generated"` clip.

### Known trade-off

The preview is a lossy-compressed derivative (bitrate undocumented by
Freesound), not the pristine original. Good enough for ambient beds; for
a flagship texture worth pristine quality, the stored Freesound sound ID
in `source_url` makes a future manual re-download via the full OAuth2
original-download endpoint a cheap follow-up, not a re-search.
