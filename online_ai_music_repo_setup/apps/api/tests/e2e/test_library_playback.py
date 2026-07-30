"""First real browser E2E test for AION's web UI.

Everything about this UI (waveform rendering, click-to-seek, and
specifically whether the persistent player bar survives a library
re-render after Approve) was repeatedly flagged throughout this project's
history as "not verified: actual in-browser behavior... could not be
clicked through" -- structural checks (element presence via TestClient)
were the only coverage. This is the first test that drives a real browser
against a real running server.

Requires the dev server running locally (see conftest.py); skipped
automatically if it isn't reachable. Not part of the default `pytest` run
(lives in tests/e2e/, run explicitly with `pytest tests/e2e/`).
"""

import time

from playwright.sync_api import Page, expect


def test_generate_play_approve_playback_survives_rerender(base_url: str, page: Page) -> None:
    # A unique title so every selector below can scope to *this* run's row
    # specifically -- the library accumulates jobs from every previous run
    # of this test (and everything else generated through the UI), so
    # ".first" or a bare ".approve-btn" locator is ambiguous and was the
    # actual cause of this test's first two failed attempts, not a real
    # app bug (confirmed separately: the generate/play/approve flow itself
    # worked correctly both times, server-side).
    unique_title = f"E2E Playback Test {time.time()}"

    page.goto(f"{base_url}/app")

    page.fill("#title", unique_title)
    page.select_option("#mode", "sine")
    page.fill("#duration", "2")

    page.click("#run-audio-only")
    expect(page.locator("#results")).to_be_visible(timeout=10_000)

    row = page.locator(".library-row", has_text=unique_title)
    # Generous timeout: this environment has a documented cold-start delay
    # on the first request to a freshly restarted server (60-150s+,
    # confirmed harmless via direct pipeline timing elsewhere this
    # session), and the library GET here can be the first such request.
    expect(row).to_be_visible(timeout=120_000)

    row.locator(".play-btn").click()

    player_bar = page.locator("#player-bar")
    global_player = page.locator("#global-player")

    expect(player_bar).not_to_have_class("hidden", timeout=10_000)
    expect(global_player).to_have_js_property("paused", False, timeout=10_000)

    approve_button = row.locator(".approve-btn")
    approve_button.click()

    # The row re-renders after Approve (status badge changes, button
    # disappears) -- wait for that specific row's approve button to be
    # gone, not "any approve button anywhere" (the library has rows left
    # over from other runs with their own pending approvals).
    expect(approve_button).to_have_count(0, timeout=15_000)

    # The actual regression this player bar was built to fix: destroying
    # and rebuilding the library rows on Approve used to destroy the
    # mid-playback <audio> element along with them.
    expect(global_player).to_have_js_property("paused", False, timeout=5_000)
    expect(player_bar).not_to_have_class("hidden")
