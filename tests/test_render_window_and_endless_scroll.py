"""Regression tests for render-window and endless-scroll improvements.

Changes under test:
  1. MESSAGE_RENDER_WINDOW_DEFAULT raised from 50 → 100 (static/ui.js)
  2. _INITIAL_MSG_LIMIT raised from 30 → 100 (static/sessions.js)
  3. session_endless_scroll default changed from False → True (api/config.py)
  4. Load-older indicator text now differentiates between endless-scroll
     enabled (scroll prompt) and disabled (click prompt), using new i18n
     keys: load_earlier_hidden, scroll_up_load_more, click_load_earlier
     (static/ui.js + static/i18n.js)

These tests pin the source-level wiring without needing a live server.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_JS = ROOT / "static" / "ui.js"
SESSIONS_JS = ROOT / "static" / "sessions.js"
I18N_JS = ROOT / "static" / "i18n.js"
CONFIG_PY = ROOT / "api" / "config.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════
#  1. Render window size
# ════════════════════════════════════════════════════════════════════

class TestRenderWindowDefault:
    def test_render_window_is_100(self):
        src = _read(UI_JS)
        assert "const MESSAGE_RENDER_WINDOW_DEFAULT=100;" in src, (
            "MESSAGE_RENDER_WINDOW_DEFAULT must be 100 (raised from 50)"
        )

    def test_initial_msg_limit_is_100(self):
        src = _read(SESSIONS_JS)
        assert "const _INITIAL_MSG_LIMIT = 100;" in src, (
            "_INITIAL_MSG_LIMIT must be 100 (raised from 30)"
        )


# ════════════════════════════════════════════════════════════════════
#  2. Endless scroll default
# ════════════════════════════════════════════════════════════════════

class TestEndlessScrollDefault:
    def test_default_is_true(self):
        src = _read(CONFIG_PY)
        # Match the specific line in _SETTINGS_DEFAULTS
        m = re.search(
            r'"session_endless_scroll"\s*:\s*(True|False)\s*,',
            src,
        )
        assert m, "session_endless_scroll setting not found in _SETTINGS_DEFAULTS"
        assert m.group(1) == "True", (
            "session_endless_scroll default must be True (changed from False)"
        )


# ════════════════════════════════════════════════════════════════════
#  3. Indicator text differentiates endless-scroll state
# ════════════════════════════════════════════════════════════════════

class TestIndicatorTextDifferentiation:
    def test_uses_load_earlier_hidden_key(self):
        """When messages are hidden in the render window, the indicator
        must use the load_earlier_hidden i18n key with {n} placeholder."""
        src = _read(UI_JS)
        assert "t('load_earlier_hidden'" in src, (
            "Indicator must use t('load_earlier_hidden') for hidden messages count"
        )
        assert "{n}" in src, (
            "load_earlier_hidden must support {n} placeholder for hidden count"
        )

    def test_uses_scroll_up_load_more_when_endless_enabled(self):
        """When endless scroll is enabled and no messages are locally hidden,
        the indicator must show the scroll-up prompt."""
        src = _read(UI_JS)
        assert "t('scroll_up_load_more'" in src, (
            "Indicator must use t('scroll_up_load_more') when endless scroll is on"
        )

    def test_uses_click_load_earlier_when_endless_disabled(self):
        """When endless scroll is disabled, the indicator must show the
        click-to-load prompt."""
        src = _read(UI_JS)
        assert "t('click_load_earlier'" in src, (
            "Indicator must use t('click_load_earlier') when endless scroll is off"
        )

    def test_branch_order_is_hidden_then_endless_check(self):
        """The ternary must check hiddenBeforeCount first, then branch
        on endless scroll state for the non-hidden case."""
        src = _read(UI_JS)
        # Find the indicator textContent assignment block
        idx = src.find("indicator.textContent=hiddenBeforeCount>0")
        assert idx > 0, "indicator.textContent ternary not found"
        block = src[idx : idx + 500]
        # hidden count branch first
        assert "hiddenBeforeCount>0" in block
        # then endless scroll check
        assert "_isSessionEndlessScrollEnabled" in block
        # then click fallback
        assert "click_load_earlier" in block


# ════════════════════════════════════════════════════════════════════
#  4. i18n keys exist in English, zh-CN, zh-TW (×2)
# ════════════════════════════════════════════════════════════════════

REQUIRED_I18N_KEYS = [
    "load_earlier_hidden",
    "scroll_up_load_more",
    "click_load_earlier",
]

# Locales that must have all three keys.
# en is the first locale, zh-CN and two zh-TW variants appear later.
LOCALE_NAMES = {
    "en": "English",
    "zh-CN": "Simplified Chinese",
    "zh-TW (Han)": "Traditional Chinese (Taiwan)",
    "zh-TW (HK)": "Traditional Chinese (Hong Kong)",
}


class TestI18nKeysPresent:
    def _find_locale_block(self, src: str, locale_label: str) -> str:
        """Extract the locale block by finding a unique anchor string.
        We use the untitled/n_messages pattern near each locale's header."""
        # Each locale has: load_older_messages: '...'
        # Find all occurrences and use surrounding context to distinguish
        anchors = {
            "en": "load_older_messages: '↑ Scroll up or click to load older messages'",
            "zh-CN": "load_older_messages: '↑ 向上滚动或点击加载更早的消息'",
            "zh-TW (Han)": "load_older_messages: '↑ 向上捲動或點擊以載入較早的訊息'",
        }
        if locale_label not in anchors:
            return ""
        anchor = anchors[locale_label]
        idx = src.find(anchor)
        if idx < 0:
            return ""
        # Grab ~2KB around the anchor — enough to contain all 3 new keys
        start = max(0, idx - 500)
        end = min(len(src), idx + 2000)
        return src[start:end]

    def test_english_keys(self):
        src = _read(I18N_JS)
        block = self._find_locale_block(src, "en")
        assert block, "English locale block not found"
        for key in REQUIRED_I18N_KEYS:
            assert f"{key}:" in block, (
                f"English locale missing key: {key}"
            )

    def test_zh_cn_keys(self):
        src = _read(I18N_JS)
        block = self._find_locale_block(src, "zh-CN")
        assert block, "zh-CN locale block not found"
        for key in REQUIRED_I18N_KEYS:
            assert f"{key}:" in block, (
                f"zh-CN locale missing key: {key}"
            )

    def test_zh_tw_keys(self):
        """Both zh-TW locale variants (Han + HK) must have the new keys."""
        src = _read(I18N_JS)
        # Find all zh-TW blocks by looking for the Traditional Chinese text
        tw_anchor = "向上捲動或點擊以載入較早的訊息"
        occurrences = []
        start = 0
        while True:
            idx = src.find(tw_anchor, start)
            if idx < 0:
                break
            block = src[max(0, idx - 500) : idx + 2000]
            occurrences.append(block)
            start = idx + len(tw_anchor)
        assert len(occurrences) >= 2, (
            f"Expected 2 zh-TW locale blocks, found {len(occurrences)}"
        )
        for i, block in enumerate(occurrences):
            for key in REQUIRED_I18N_KEYS:
                assert f"{key}:" in block, (
                    f"zh-TW locale block #{i + 1} missing key: {key}"
                )

    def test_load_earlier_hidden_has_placeholder(self):
        """All load_earlier_hidden translations must include the {n}
        placeholder for the hidden-count substitution."""
        src = _read(I18N_JS)
        matches = re.findall(
            r"load_earlier_hidden:\s*'([^']*)'", src
        )
        assert len(matches) >= 4, (
            f"Expected 4+ load_earlier_hidden translations, found {len(matches)}"
        )
        for m in matches:
            assert "{n}" in m, (
                f"load_earlier_hidden must contain {{n}} placeholder, got: {m!r}"
            )


# ════════════════════════════════════════════════════════════════════
#  5. Settings description for endless scroll exists
# ════════════════════════════════════════════════════════════════════

class TestEndlessScrollSettingsI18n:
    def test_settings_desc_in_zh_cn(self):
        src = _read(I18N_JS)
        assert "settings_desc_session_endless_scroll" in src
        # Verify the zh-CN translation exists
        idx = src.find("向上滚动时加载更早的消息")
        assert idx > 0, "zh-CN endless scroll label not found"
        # Description should be nearby
        nearby = src[idx : idx + 300]
        assert "settings_desc_session_endless_scroll" in nearby or \
               "启用后" in nearby, (
            "zh-CN endless scroll description not found near label"
        )

    def test_settings_toggle_exists_in_html(self):
        """The settings panel HTML must have the toggle for endless scroll."""
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        assert "session_endless_scroll" in html, (
            "Settings panel must include session_endless_scroll toggle"
        )
        assert "settings_label_session_endless_scroll" in html, (
            "Settings panel must reference the i18n label key"
        )
