"""Tests for administrative boilerplate removal."""

from foa_pipeline.normalisation.boilerplate import (
    ALL_GROUPS,
    DEFAULT_GROUPS,
    MIN_RESULT_CHARS,
    boilerplate_stats,
    strip_boilerplate,
)

# Long enough to clear MIN_RESULT_CHARS so the fail-safe doesn't mask results.
RESEARCH_TEXT = (
    "The Sociology Program supports basic research on all forms of human social "
    "organization, including social movements, stratification and mobility, and "
    "population dynamics. The program supports both original data collection and "
    "secondary analysis using quantitative and qualitative methodological tools."
)


class TestMarkupRemoval:
    def test_strips_html_tags(self):
        result = strip_boilerplate(f'<ul type="disc"><li>{RESEARCH_TEXT}</li></ul>')
        assert "<ul" not in result
        assert "<li>" not in result
        assert "Sociology Program" in result

    def test_strips_attribute_values_not_just_tag_names(self):
        """href URLs and attribute values are tokens the taggers would see."""
        text = f'{RESEARCH_TEXT} <a href="https://www.sbir.gov/eligibility">Guide</a>'
        result = strip_boilerplate(text)
        assert "sbir.gov" not in result
        assert "href" not in result
        assert "Guide" in result  # link text is real content, kept

    def test_strips_html_entities(self):
        result = strip_boilerplate(f"{RESEARCH_TEXT}&nbsp;&amp;&#8212;")
        assert "&nbsp;" not in result
        assert "&amp;" not in result

    def test_preserves_prose_unchanged(self):
        assert strip_boilerplate(RESEARCH_TEXT) == RESEARCH_TEXT


class TestOptionalGroups:
    """Not enabled by default, but must still work when explicitly requested."""

    def test_eligibility_block_removed_when_requested(self):
        text = (
            f"{RESEARCH_TEXT} *Who May Submit Proposals: Proposals may only be "
            "submitted by the following: -Institutions of Higher Education (IHEs):"
        )
        result = strip_boilerplate(text, groups=["eligibility"])
        assert "Who May Submit" not in result
        assert "Sociology Program" in result

    def test_deadline_table_removed_when_requested(self):
        text = (
            f"{RESEARCH_TEXT} Upcoming due dates Full proposal 2026 July 27 2026 - "
            "Deadline date November 4 2026 - Deadline date First Wednesday in "
            "November, Annually Thereafter"
        )
        result = strip_boilerplate(text, groups=["deadlines"])
        assert "Deadline date" not in result
        assert "Sociology Program" in result

    def test_pappg_reference_removed_when_requested(self):
        text = f"{RESEARCH_TEXT} For conference proposals, please refer to PAPPG Chapter II.E.9."
        result = strip_boilerplate(text, groups=["procedural"])
        assert "PAPPG" not in result
        assert "Sociology Program" in result

    def test_default_groups_leave_optional_boilerplate_alone(self):
        """Guards the measured decision: only markup is on by default."""
        text = f"{RESEARCH_TEXT} *Who May Submit Proposals: Deadline date November 4"
        assert "Who May Submit" in strip_boilerplate(text)
        assert DEFAULT_GROUPS == ("markup",)


class TestOverStrippingGuards:
    """Losing real text silently costs recall, so the fail-safes matter."""

    def test_returns_original_when_stripping_would_gut_the_text(self):
        text = '<ul type="disc"><li><a href="http://x.example/a">go</a></li></ul>'
        result = strip_boilerplate(text, groups=ALL_GROUPS)
        # Almost everything here is markup; rather than emit a fragment,
        # the original is preserved.
        assert len(result) > 0

    def test_short_result_falls_back_to_original(self):
        text = "<p>Short.</p>"
        result = strip_boilerplate(text)
        assert len(result) < MIN_RESULT_CHARS
        assert "Short." in result

    def test_never_returns_empty_for_nonempty_input(self):
        for text in ["<div></div>", "&nbsp;&nbsp;", "<a href='http://x.example'></a>"]:
            assert strip_boilerplate(text) != ""

    def test_handles_none_and_empty(self):
        assert strip_boilerplate(None) == ""
        assert strip_boilerplate("") == ""


class TestStats:
    def test_reports_per_group_character_counts(self):
        text = f'<p>{RESEARCH_TEXT}</p> *Who May Submit Proposals: refer to PAPPG Chapter II.'
        stats = boilerplate_stats(text)
        assert set(stats) == set(ALL_GROUPS)
        assert stats["markup"] > 0
        assert stats["eligibility"] > 0

    def test_zero_for_clean_text(self):
        assert all(v == 0 for v in boilerplate_stats(RESEARCH_TEXT).values())

    def test_handles_empty(self):
        assert boilerplate_stats("") == {g: 0 for g in ALL_GROUPS}
