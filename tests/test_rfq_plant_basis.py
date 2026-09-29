"""사양서의 비교값 — 지금 설비에서 셈했는가 (1.4 · 3.5 · 3.6 · 6.7).

포락선이 2,400 × 1,200 에서 2,500 × 1,400 으로, 램프가 40 등 100 kW 에서
48 등 120 kW 로 바뀐 뒤에도 사양서에는 그 이전 설비로 셈한 비교값이 세 곳
남아 있었다:

  · 1.4 확장 여지 — 'IR 100 → 200 kW'. 출발이 40 등이었다
    (tests/test_dg_hk60_rfq.py 의 확장 조항 시험이 검토서 채택안과 잇는다)
  · 3.5 변경 전후 표 — 4.403 → 2.893 MJ · 126 → 83 kW · 여유 15.7 → 44.6 %.
    2,400 × 1,200 · 60 등 150 kW 로 셈한 값이었다. 같은 문서 3.6항은 같은
    140 °C 에서 여유 17.0 % 를 말하고 있었다
  · 6.7 배기 — '150 kW IR'. 고도화 이전 REV.20 의 값인데, 이 사양서에서
    '선행' 은 인계되는 REV.21C 를 가리키므로 입찰자는 지금 설비로 읽는다

3.5 를 지금 설비로 다시 셈하자 표의 결론이 바뀌었다 — 종전 200 °C 였다면
120 kW 로는 칼날을 따라가지 못한다(여유 −26.3 %). '처리량은 칼날이 정하므로
불변' 은 150 kW 에서만 참이었다. 그리고 3.6 의 근거식과 콘솔 주석은 탠덤
칼날 사이클(55.4 s)로 셈한 여유(16.9 · 2.4 · 18.6 %)를 지금 칼날의 17.0 %
옆에 두고 있었다 — 한 줄 안에서 칼날이 둘이었다.

사양서와 콘솔 주석은 손으로 쓴다. 그래서 값을 사이클 거울(tools/cycle.py)로
다시 셈해 대조한다 — 설비가 바뀌면 여기가 먼저 깨진다.
"""

import re
import unittest

from . import _path  # noqa: F401
from ._path import ROOT

import cycle as CY  # noqa: E402
from console_consts import const as c  # noqa: E402

RFQ = ROOT / "docs" / "dg-hk60-rfq.html"
CONSOLE = ROOT / "docs" / "drawings" / "pv-delamination-3d.html"

MINUS = "−"                      # 사양서는 음수에 수학 기호 − 를 쓴다
LAMPS = int(c("LAMPS"))
LAMP_KW = CY.DEFAULT["lampPower"]
RATED = LAMPS * LAMP_KW


def _text(path):
    return path.read_text(encoding="utf-8")


def _flat(s):
    return re.sub(r"\s+", " ", s)


def _signed(x):
    return (MINUS if x < 0 else "") + f"{abs(x):.1f}"


def margin(m):
    """열공정 여유 % — 방출피치가 칼날 사이클보다 얼마나 짧은가. 음수면 가열이 병목."""
    return (1 - m["pitch"] / m["knifeCycle"]) * 100


def need_kw(m):
    """칼날 사이클을 따라가는 데 드는 IR 평균 — Q / (η · 칼날 사이클)."""
    return m["q"] / m["eta"] / m["knifeCycle"]


def _clause(html, n):
    m = re.search(rf'<div class="n">{re.escape(n)}</div>(.*?)\n  </div></div>', html, re.S)
    assert m, f"{n} 조항이 없다"
    return m.group(1)


class TestTheTemperatureTableIsThisPlant(unittest.TestCase):
    """3.5 변경 전후 — 같은 설비에서 온도만 바꾼 값인가."""

    @classmethod
    def setUpClass(cls):
        cls.html = _text(RFQ)
        m = re.search(r"<caption>변경 전후.*?</table>", cls.html, re.S)
        assert m, "3.5 변경 전후 표가 없다"
        cls.table = m.group(0)
        cls.rows = {}
        for name, old, new, note in re.findall(
                r'<tr><th>([^<]+)</th><td class="num">([^<]+)</td>'
                r'<td class="num">([^<]+)</td>\s*<td>(.*?)</td></tr>', cls.table, re.S):
            cls.rows[name] = (old, new, _flat(note))
        t_old, t_new = cls.rows["EVA/유리 계면 목표"][:2]
        cls.t_old = int(t_old.split()[0])
        cls.t_new = int(t_new.split()[0])
        cls.dt_old = cls.t_old - c("T_AMB")
        cls.dt_new = cls.t_new - c("T_AMB")
        cls.old = CY.model(plant={"dT": cls.dt_old})
        cls.new = CY.model()

    def test_the_new_column_is_the_console_target(self):
        self.assertEqual(self.t_new, c("T_TARGET"), "표의 변경 온도가 콘솔 목표와 다르다")
        self.assertEqual(self.dt_new, CY.MODEL["dT"])
        self.assertIn(f"ΔT {self.dt_old:.0f} → {self.dt_new:.0f} K",
                      self.rows["EVA/유리 계면 목표"][2])

    def test_the_caption_names_the_plant_it_was_priced_on(self):
        """어느 설비로 셈했는지 적지 않은 비교표는 설비가 바뀌어도 티가 안 난다."""
        cap = _flat(re.search(r"<caption>(.*?)</caption>", self.table, re.S).group(1))
        L, W = c("PANEL_L") * 1000, c("PANEL_W") * 1000
        for token in (f"포락선 {L:,.0f} × {W:,.0f}", f"{LAMPS} 등 {RATED:.0f} kW",
                      f"η {self.new['eta']:.2f}",
                      f"칼날 사이클 {self.new['knifeCycle']:.1f} s", "온도만 바꾼"):
            self.assertIn(token, cap, f"표 제목이 셈한 설비를 밝히지 않는다: {token}")

    def test_heat_per_panel(self):
        old, new, note = self.rows["패널당 열량"]
        self.assertEqual((old, new), (f"{self.old['q'] / 1000:.3f} MJ",
                                      f"{self.new['q'] / 1000:.3f} MJ"))
        drop = round((1 - self.new["q"] / self.old["q"]) * 100)
        self.assertIn(f"{MINUS}{drop} %", note)
        # 3.5 표와 5.1항 열모델이 같은 Q 를 말한다
        self.assertIn(f"→ {self.new['q'] / 1000:.3f} MJ/장", self.html)

    def test_ir_average_is_what_following_the_knife_takes(self):
        old, new, note = self.rows["IR 평균전력"]
        self.assertEqual((old, new), (f"{need_kw(self.old):.1f} kW",
                                      f"{need_kw(self.new):.1f} kW"))
        # 종전 값은 설치정격을 넘는다 — 표가 그렇다고 말해야 한다
        self.assertGreater(need_kw(self.old), RATED)
        self.assertLess(need_kw(self.new), RATED)
        self.assertIn(f'설치 <span class="m">{RATED:.0f} kW</span>를 넘는다', note)
        # 3.6항 주석의 평균전력과 같은 값이다
        self.assertIn(f'<code>Q / (η · 사이클)</code> = <span class="m">'
                      f'{need_kw(self.new):.1f} kW</span>', self.html)

    def test_margin_and_what_the_old_temperature_would_have_cost(self):
        old, new, note = self.rows["열공정 여유"]
        self.assertEqual((old, new), (f"{_signed(margin(self.old))} %",
                                      f"{_signed(margin(self.new))} %"))
        self.assertLess(margin(self.old), 0, "종전 온도에서도 가열이 칼날을 따라간다")
        # 가열이 병목일 때의 처리량 — 계약에 못 미친다는 말이 참이어야 한다
        rate = self.old["thermalRate"]
        net = rate * CY.AVAILABILITY
        self.assertLess(net, CY.NET_TARGET)
        self.assertIn(f'명목 <span class="m">{rate:.1f} 장/h</span>(순생산 {net:.1f})', note)
        self.assertIn(f"계약 {CY.NET_TARGET} 장/h", note)
        # 같은 여유를 지키는 설치전력은 ΔT 비로 늘어난다 — 계산으로 확인한다
        scaled = RATED * self.dt_old / self.dt_new
        self.assertIn(f'{RATED:.0f} × {self.dt_old:.0f} / {self.dt_new:.0f} = '
                      f'<span class="m">{scaled:.1f} kW</span>', note)
        same = CY.model(plant={"dT": self.dt_old}, lampPower=LAMP_KW * scaled / RATED)
        self.assertAlmostEqual(margin(same), margin(self.new), places=9)
        self.assertIn(f"{LAMPS} 등 {RATED:.0f} kW 는 {self.t_new} °C 에서 정한 값", note)

    def test_cassette_changeover(self):
        knife_old, knife_new = self.rows["계단 칼날 (유리 계면)"][:2]
        lo, hi = (int(x) for x in re.findall(r"\d+", knife_old))
        self.assertEqual(int(knife_new.split()[0]), c("T_KNIFE"))

        def auto_min(t_hot):
            heat = (c("CASS_MASS") * c("CASS_CP") * 1e3 * (t_hot - c("CASS_T_PRE"))
                    / (c("CASS_HEAT_KW") * 1e3 * c("CASS_HEAT_ETA")))
            return (c("CASS_SWAP_AUTO") + heat) / 60

        old, new, note = self.rows["카세트 자동교환 정지"]
        self.assertEqual((old, new), (f"{auto_min(lo):.1f} – {auto_min(hi):.1f} 분",
                                      f"{auto_min(c('T_KNIFE')):.1f} 분"))
        self.assertIn(f"예열 포켓 {c('CASS_T_PRE'):.0f} °C", note)

    def test_no_row_is_left_from_the_old_plant(self):
        for s in ("4.403", "2.893 MJ", "126 kW", "83 kW", "15.7 %", "44.6 %",
                  "4.5 분", "처리량은 칼날이 정하므로 불변"):
            self.assertNotIn(s, self.table, f"3.5 표에 옛 설비의 '{s}' 가 남아 있다")


class TestTheSizingChainIsOneKnife(unittest.TestCase):
    """3.6 설치전력 근거식 — 한 줄 안의 여유들이 같은 칼날 사이클에서 나왔는가."""

    @classmethod
    def setUpClass(cls):
        body = _clause(_text(RFQ), "3.6")
        cls.logic = _flat(re.search(r'<div class="logic">(.*?)</div>', body, re.S).group(1))
        cls.now = CY.model()
        cls.old_env = CY.model(panelLength=2400, panelWidth=1200, plant={"lamps": 40})
        cls.lamps40 = CY.model(plant={"lamps": 40})

    def test_every_margin_is_the_current_knife(self):
        n, o, f = self.now, self.old_env, self.lamps40
        for token in (
                f"{LAMPS} 등 {RATED:.0f} kW 에서 열공정 여유 {margin(n):.1f} %",
                f"같은 칼날로 2,400 × 1,200 · 40 등 {40 * LAMP_KW:.0f} kW 는 여유 {margin(o):.1f} %",
                f"Q +{(n['q'] / o['q'] - 1) * 100:.1f} %",
                f"사이클 +{n['knifeCycle'] - o['knifeCycle']:.1f} s",
                f"{40 * LAMP_KW:.0f} kW 그대로면 여유가 {margin(f):.1f} % 로 무너진다"):
            self.assertIn(token, self.logic, f"3.6 근거식이 지금 칼날의 값과 다르다: {token}")

    def test_no_tandem_era_margin_is_left(self):
        """16.9 · 2.4 % 는 탠덤 사이클 55.4 s 의 값이다 — 17.0 % 와 한 줄에 둘 수 없다."""
        self.assertAlmostEqual(CY.model(knife_depth=300)["knifeLineCycle"], 55.4, delta=.05)
        for s in ("16.9 %", "2.4 %", "시절"):
            self.assertNotIn(s, self.logic, f"3.6 근거식에 탠덤 시절의 '{s}' 가 남아 있다")


class TestTheExhaustClauseNamesItsPlant(unittest.TestCase):
    """6.7 — 옛 정격은 옛 설비의 이름을 달고, 납품 설비의 정격을 함께 말한다."""

    @classmethod
    def setUpClass(cls):
        cls.html = _text(RFQ)
        cls.body = _flat(_clause(cls.html, "6.7"))

    def test_the_old_rating_is_labelled_rev20(self):
        # REV.20 의 계산 모델은 '뱅크 = 단수 + 1, 뱅크당 10 등' 으로 5단 60 등이었다
        m = re.search(r'선행 설계\(<span class="k">REV\.20</span> · IR '
                      r'<span class="m">(\d+) 등 (\d+) kW</span>\)', self.body)
        self.assertIsNotNone(m, "6.7 의 옛 IR 정격이 어느 설비의 것인지 밝히지 않는다")
        self.assertEqual(int(m.group(2)), round(int(m.group(1)) * LAMP_KW))
        self.assertNotIn('<span class="m">150 kW</span> IR', self.html,
                         "설비 이름 없이 옛 정격을 적은 문장이 남아 있다")

    def test_the_delivered_rating_is_stated(self):
        self.assertIn(f'납품 설비의 IR 은 <span class="m">{LAMPS} 등 {RATED:.0f} kW</span>다',
                      self.body)


class TestTheConsoleNotesQuoteTheirOwnModel(unittest.TestCase):
    """콘솔 주석도 손으로 쓴다 — 3.5 · 3.6 과 같은 숫자가 같은 이유로 틀려 있었다."""

    @classmethod
    def setUpClass(cls):
        cls.src = _flat(_text(CONSOLE))
        cls.now = CY.model()
        cls.old = CY.model(plant={"dT": 200 - c("T_AMB")})
        cls.old_env = CY.model(panelLength=2400, panelWidth=1200, plant={"lamps": 40})
        cls.lamps40 = CY.model(plant={"lamps": 40})

    def test_the_temperature_note(self):
        o, n = self.old, self.now
        for token in (f"q 는 {o['q'] / 1000:.2f} → {n['q'] / 1000:.2f} MJ/장",
                      f"IR 평균은 {need_kw(o):.1f} → {need_kw(n):.1f} kW",
                      f"여유 {_signed(margin(o))}% → {_signed(margin(n))}%"):
            self.assertIn(token, self.src, f"콘솔 공정 온도 주석이 모델과 다르다: {token}")

    def test_the_sizing_note(self):
        for token in (f"40등 100kW 가 여유 {margin(self.old_env):.1f}% 다",
                      f"여유가 {margin(self.lamps40):.1f}% 로 무너진다",
                      f"{LAMPS}등 {RATED:.0f}kW — 여유 {margin(self.now):.1f}%",
                      f"평균 소비전력은 {need_kw(self.now):.1f}kW"):
            self.assertIn(token, self.src, f"콘솔 가열실 규모 주석이 모델과 다르다: {token}")

    def test_no_old_note_is_left(self):
        for s in ("4.40 → 2.89", "126 → 83", "여유 16.9%", "2.4% 로", "여유 18.6%", "97.6kW"):
            self.assertNotIn(s, self.src, f"콘솔 주석에 옛 설비의 '{s}' 가 남아 있다")


if __name__ == "__main__":
    unittest.main()
