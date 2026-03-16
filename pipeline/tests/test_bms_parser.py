"""Tests for bms_parser.py — BMS map parsing and screen flow analysis."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bms_parser import parse_bms_file, ScreenFlowIndex


def _write_bms(tmp_dir, name, content):
    p = Path(tmp_dir) / f"{name}.bms"
    p.write_text(content, encoding="utf-8")
    return p


class TestBmsParsing:
    def test_parses_mapset_and_map(self, tmp_path):
        _write_bms(tmp_path, "TESTMS", """
TESTMS  DFHMSD CTRL=(ALARM,FREEKB),LANG=COBOL,MODE=INOUT,TYPE=&&SYSPARM
TESTM1A DFHMDI COLUMN=1,LINE=1,SIZE=(24,80)
TITLE   DFHMDF ATTRB=(ASKIP,NORM),LENGTH=10,POS=(1,1),INITIAL='Hello'
NAMEFLD DFHMDF ATTRB=(UNPROT,NORM),LENGTH=20,POS=(3,10),COLOR=GREEN
        DFHMSD TYPE=FINAL
        END
""")
        ms = parse_bms_file(tmp_path / "TESTMS.bms")
        assert ms is not None
        assert ms.name == "TESTMS"
        assert len(ms.maps) == 1
        assert ms.maps[0].name == "TESTM1A"
        assert ms.maps[0].rows == 24
        assert ms.maps[0].cols == 80

    def test_identifies_input_fields(self, tmp_path):
        _write_bms(tmp_path, "INPMS", """
INPMS   DFHMSD LANG=COBOL,TYPE=&&SYSPARM
INPM1A  DFHMDI SIZE=(24,80)
INP1    DFHMDF ATTRB=(UNPROT,NORM),LENGTH=20,POS=(1,7)
INP2    DFHMDF ATTRB=(IC,NORM),LENGTH=10,POS=(2,7)
OUT1    DFHMDF ATTRB=(PROT,NORM),LENGTH=15,POS=(3,7)
        DFHMSD TYPE=FINAL
        END
""")
        ms = parse_bms_file(tmp_path / "INPMS.bms")
        m = ms.maps[0]
        assert len(m.input_fields) == 2
        assert m.input_fields[0].name == "INP1"
        assert m.input_fields[1].name == "INP2"

    def test_extracts_colors_and_attributes(self, tmp_path):
        _write_bms(tmp_path, "COLMS", """
COLMS   DFHMSD LANG=COBOL,TYPE=&&SYSPARM
COLM1A  DFHMDI SIZE=(24,80)
FLD1    DFHMDF ATTRB=(ASKIP,BRT),COLOR=RED,LENGTH=20,POS=(5,10)
        DFHMSD TYPE=FINAL
        END
""")
        ms = parse_bms_file(tmp_path / "COLMS.bms")
        f = ms.maps[0].fields[0]
        assert f.color == "RED"
        assert "BRT" in f.attributes


class TestScreenFlowIndex:
    def test_loads_real_carddemo(self):
        carddemo = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
        if not carddemo.exists():
            return
        sfi = ScreenFlowIndex(str(carddemo))
        s = sfi.summary()
        assert s["total_mapsets"] > 10
        assert s["total_input_fields"] > 50
        assert s["programs_with_screens"] > 10
        assert s["screen_transitions"] > 0

    def test_screen_flow_graph(self):
        carddemo = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
        if not carddemo.exists():
            return
        sfi = ScreenFlowIndex(str(carddemo))
        flow = sfi.screen_flow()
        assert len(flow["nodes"]) > 0
        assert len(flow["edges"]) > 0
        edge_types = {e["type"] for e in flow["edges"]}
        assert "XCTL" in edge_types or "NAVIGATE" in edge_types

    def test_ascii_rendering(self):
        carddemo = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
        if not carddemo.exists():
            return
        sfi = ScreenFlowIndex(str(carddemo))
        ascii_art = sfi.render_screen_ascii("COSGN00")
        assert ascii_art is not None
        assert "USERID" in ascii_art or "________" in ascii_art

    def test_screen_detail(self):
        carddemo = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
        if not carddemo.exists():
            return
        sfi = ScreenFlowIndex(str(carddemo))
        detail = sfi.screen_detail("COSGN00")
        assert detail is not None
        assert detail["programs"]
        assert detail["maps"][0]["input_fields"]
