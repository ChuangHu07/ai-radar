"""The accepted current-paper scenes must resolve to usable SVG assets."""

from pathlib import Path
import xml.etree.ElementTree as ET

from app.reading.overview_visual import visual_for_paper


ROOT = Path(__file__).resolve().parents[1]
CURRENT_IDS = ('2610.13948', '2610.13935', '2610.13909', '2610.13895', '2610.13889')


def test_current_overview_papers_have_distinct_valid_scenes():
    themes = []
    for paper_id in CURRENT_IDS:
        visual = visual_for_paper({'paper_id': paper_id})
        assert visual and visual['kind'] == 'concept_illustration'
        assert visual['caption_zh'] and visual['caption_en']
        themes.append(visual['theme'])
        for suffix in ('', '-mobile', '-preview'):
            asset = ROOT / 'frontend' / 'public' / 'overview-visuals' / f'{visual["theme"]}{suffix}.svg'
            assert asset.is_file()
            assert ET.parse(asset).getroot().tag.endswith('svg')
    assert len(set(themes)) == len(CURRENT_IDS)
