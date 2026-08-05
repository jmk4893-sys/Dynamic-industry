const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5

// ---- Brand palette (extracted from source IR deck) ----
const DARK = "1B4D3E";      // deep forest green (title/closing bg)
const DARK2 = "28604C";     // lighter panel on dark
const GREEN = "2E8B57";     // primary green
const GREEN_LT = "589C78";  // orbit lines on dark
const MINT = "CDE8D8";      // light mint text on dark
const AMBER = "F5B325";     // accent
const INK = "2D3E36";       // body text
const MUTED = "6E8478";     // muted text
const TINT = "E4F2E9";      // light green tint
const CARD = "F7FBF8";      // card bg
const BORDER = "DCE8E0";    // card border
const RED = "C0504D";       // loss bars
const W = 13.333, H = 7.5;

const FONT = "맑은 고딕";

function footer(slide, num) {
  slide.addText("인도 태양광 패널 재활용  ·  Elevator Pitch", {
    x: 0.55, y: 7.06, w: 5.5, h: 0.3, fontFace: FONT, fontSize: 9,
    color: MUTED, margin: 0, align: "left",
  });
  slide.addText(String(num), {
    x: 12.55, y: 7.06, w: 0.5, h: 0.3, fontFace: FONT, fontSize: 9,
    color: MUTED, margin: 0, align: "right",
  });
}

function header(slide, tag, title) {
  slide.addText("DYNAMIC INDUSTRY", {
    x: 0.55, y: 0.32, w: 4.0, h: 0.3, fontFace: FONT, fontSize: 11,
    bold: true, color: DARK, charSpacing: 2, margin: 0,
  });
  slide.addText(tag, {
    x: 9.3, y: 0.32, w: 3.45, h: 0.3, fontFace: FONT, fontSize: 10,
    bold: true, color: AMBER, align: "right", charSpacing: 1, margin: 0,
  });
  slide.addText(title, {
    x: 0.55, y: 0.72, w: 12.2, h: 0.75, fontFace: FONT, fontSize: 27,
    bold: true, color: INK, margin: 0,
  });
}

function orbit(slide, cx, cy, radii) {
  radii.forEach((r) => {
    slide.addShape("ellipse", {
      x: cx - r, y: cy - r, w: r * 2, h: r * 2,
      fill: { type: "none" },
      line: { color: GREEN_LT, width: 0.75, transparency: 35 },
    });
  });
}

function statCard(slide, x, y, w, h, value, label, valColor) {
  slide.addShape("roundRect", {
    x, y, w, h, rectRadius: 0.07,
    fill: { color: "FFFFFF" }, line: { color: BORDER, width: 1 },
    shadow: { type: "outer", color: "1B4D3E", opacity: 0.10, blur: 6, offset: 2, angle: 90 },
  });
  slide.addText(value, {
    x: x + 0.15, y: y + 0.18, w: w - 0.3, h: h * 0.5, fontFace: FONT,
    fontSize: 30, bold: true, color: valColor || GREEN, align: "center", margin: 0,
  });
  slide.addText(label, {
    x: x + 0.15, y: y + h * 0.58, w: w - 0.3, h: h * 0.36, fontFace: FONT,
    fontSize: 11.5, color: MUTED, align: "center", margin: 0, valign: "top",
  });
}

// ============================================================
// SLIDE 1 — HOOK (dark)
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: DARK };
  orbit(s, 11.4, 1.35, [1.15, 1.85, 2.6]);
  s.addShape("ellipse", { x: 10.62, y: 0.55, w: 0.16, h: 0.16, fill: { color: AMBER }, line: { type: "none" } });

  s.addText("DYNAMIC INDUSTRY", {
    x: 0.85, y: 0.75, w: 6, h: 0.4, fontFace: FONT, fontSize: 15, bold: true,
    color: "FFFFFF", charSpacing: 3, margin: 0,
  });
  s.addText("SOLAR PANEL RECYCLING · INDIA", {
    x: 0.85, y: 1.18, w: 6, h: 0.3, fontFace: FONT, fontSize: 10.5,
    color: GREEN_LT, charSpacing: 2, margin: 0,
  });

  s.addText([
    { text: "폐패널은 쓰레기가 아니라\n", options: { color: "FFFFFF" } },
    { text: "고품위 은광석", options: { color: AMBER } },
    { text: "입니다", options: { color: "FFFFFF" } },
  ], {
    x: 0.85, y: 2.35, w: 10.5, h: 2.1, fontFace: FONT, fontSize: 44, bold: true,
    lineSpacing: 58, margin: 0, valign: "top",
  });

  s.addText(
    "인도 태양광 패널 재활용 — 화학공정 없는 물리선별로 은 98%를 회수해,\n모두가 적자인 시장에서 유일한 흑자 방정식을 만듭니다.",
    {
      x: 0.85, y: 4.55, w: 10.2, h: 1.0, fontFace: FONT, fontSize: 16,
      color: MINT, lineSpacing: 26, margin: 0, valign: "top",
    }
  );

  // key hook stats row
  const hook = [
    ["570 kt", "2030 인도 c-Si 폐패널"],
    ["0 개", "상업 경쟁시설"],
    ["98%", "은 회수율 · 화학공정 0"],
    ["1.4 년", "투자 회수기간"],
  ];
  hook.forEach((d, i) => {
    const x = 0.85 + i * 3.02;
    s.addShape("roundRect", {
      x, y: 5.75, w: 2.78, h: 1.05, rectRadius: 0.06,
      fill: { color: DARK2 }, line: { type: "none" },
    });
    s.addText(d[0], {
      x: x + 0.1, y: 5.85, w: 2.58, h: 0.5, fontFace: FONT, fontSize: 21,
      bold: true, color: i === 2 ? AMBER : "FFFFFF", align: "center", margin: 0,
    });
    s.addText(d[1], {
      x: x + 0.1, y: 6.38, w: 2.58, h: 0.35, fontFace: FONT, fontSize: 10,
      color: MINT, align: "center", margin: 0,
    });
  });

  s.addText("정명근 Co-founder   ·   2026. 8   ·   투자 검토 목적 한정", {
    x: 0.85, y: 7.02, w: 8, h: 0.3, fontFace: FONT, fontSize: 9.5, color: GREEN_LT, margin: 0,
  });
}

// ============================================================
// SLIDE 2 — PROBLEM / MARKET
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "01 · 시장과 문제", "물량은 확정적으로 쌓이는데, 처리할 곳이 없다");

  statCard(s, 0.55, 1.75, 3.99, 1.7, "570 kt", "2030년 인도 c-Si 폐패널\n(9,000t/년 설비 63기 규모)");
  statCard(s, 4.67, 1.75, 3.99, 1.7, "0 개", "c-Si 상업 처리시설 —\n시장이 통째로 비어 있다");
  statCard(s, 8.79, 1.75, 3.99, 1.7, "-₹10,230/t", "기존 기계식의 톤당 손실\n(CEEW 2025 실측)", RED);

  // why incumbents lose money
  s.addShape("roundRect", {
    x: 0.55, y: 3.8, w: 7.4, h: 2.85, rectRadius: 0.07,
    fill: { color: CARD }, line: { color: BORDER, width: 1 },
  });
  s.addText("왜 모두 적자인가 — 적자의 해부", {
    x: 0.85, y: 4.02, w: 6.8, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  const anat = [
    ["은 회수율 0%", "기계식은 모듈 가치의 절반(은)을 통째로 버리고 유리·알루미늄만 판매", RED],
    ["원가의 79%가 역물류", "폐모듈 바이백 68% + 수거·운송 11% (CEEW P1 원가 구성)", INK],
    ["병목은 피드스톡 경제학", "처리 기술의 문제가 아니다 — 은을 못 꺼내는 한 적자는 필연", INK],
  ];
  anat.forEach((a, i) => {
    const y = 4.52 + i * 0.7;
    s.addShape("ellipse", { x: 0.9, y: y + 0.09, w: 0.12, h: 0.12, fill: { color: a[2] === RED ? RED : GREEN }, line: { type: "none" } });
    s.addText([
      { text: a[0] + "  —  ", options: { bold: true, color: a[2] } },
      { text: a[1], options: { color: INK } },
    ], {
      x: 1.2, y, w: 6.55, h: 0.6, fontFace: FONT, fontSize: 12.5, lineSpacing: 19, margin: 0, valign: "top",
    });
  });

  // ore-grade comparison
  s.addShape("roundRect", {
    x: 8.15, y: 3.8, w: 4.63, h: 2.85, rectRadius: 0.07,
    fill: { color: TINT }, line: { type: "none" },
  });
  s.addText("그런데 이 '쓰레기'의 은 함량은", {
    x: 8.45, y: 4.02, w: 4.05, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  s.addText([
    { text: "300~500 ppm", options: { fontSize: 30, bold: true, color: GREEN } },
    { text: "\n1차 은광 채굴한계품위(100~150ppm)의 2~5배.\n채굴이 필요 없는 광석이 지표에 쌓이고 있다 — 1톤당 함유 은 가치 약 $1,000.", options: { fontSize: 12, color: INK } },
  ], {
    x: 8.45, y: 4.45, w: 4.05, h: 2.05, fontFace: FONT, lineSpacing: 21, margin: 0, valign: "top",
  });

  footer(s, 2);
}

// ============================================================
// SLIDE 3 — SOLUTION
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "02 · 솔루션", "화학공정 없이 은 98% 회수 — 단위경제가 뒤집힌다");

  // left: recovery comparison
  s.addShape("roundRect", {
    x: 0.55, y: 1.75, w: 5.6, h: 3.6, rectRadius: 0.07,
    fill: { color: CARD }, line: { color: BORDER, width: 1 },
  });
  s.addText("소재 회수율 — 당사 vs 기존 기계식", {
    x: 0.85, y: 1.95, w: 5.0, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  const rec = [
    ["은 (Ag)", 98, 0],
    ["구리 (Cu)", 98.4, 95],
    ["유리", 99.3, 89],
    ["알루미늄", 99.6, 99],
  ];
  rec.forEach((r, i) => {
    const y = 2.42 + i * 0.68;
    s.addText(r[0], {
      x: 0.85, y, w: 1.25, h: 0.3, fontFace: FONT, fontSize: 11.5, bold: true, color: INK, margin: 0, valign: "middle",
    });
    const bw = 3.0;
    // ours
    s.addShape("roundRect", {
      x: 2.2, y: y + 0.01, w: Math.max(bw * r[1] / 100, 0.05), h: 0.24, rectRadius: 0.03,
      fill: { color: GREEN }, line: { type: "none" },
    });
    s.addText(`${r[1]}%`, {
      x: 5.25, y: y - 0.02, w: 0.75, h: 0.3, fontFace: FONT, fontSize: 11, bold: true, color: GREEN, margin: 0, valign: "middle",
    });
    // theirs
    s.addShape("roundRect", {
      x: 2.2, y: y + 0.3, w: Math.max(bw * r[2] / 100, 0.05), h: 0.14, rectRadius: 0.02,
      fill: { color: "C9D6CE" }, line: { type: "none" },
    });
    s.addText(r[2] === 0 ? "0%" : `${r[2]}%`, {
      x: 5.25, y: y + 0.24, w: 0.75, h: 0.24, fontFace: FONT, fontSize: 9, color: MUTED, margin: 0, valign: "middle",
    });
  });

  // right: unit economics flip chart (native)
  s.addShape("roundRect", {
    x: 6.45, y: 1.75, w: 6.33, h: 3.6, rectRadius: 0.07,
    fill: { color: CARD }, line: { color: BORDER, width: 1 },
  });
  s.addText("톤당 손익 (₹/t) — 적자 시장의 유일한 흑자", {
    x: 6.75, y: 1.95, w: 5.8, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  s.addChart(pres.ChartType.bar, [
    {
      name: "톤당 손익",
      labels: ["기계식 P1\n(CEEW)", "화학식 P2\n(CEEW)", "Dynamic\nIndustry"],
      values: [-10230, -12341, 84200],
    },
  ], {
    x: 6.7, y: 2.35, w: 5.85, h: 2.9,
    barDir: "col",
    chartColors: [RED, RED, GREEN],
    chartColorsOpacity: 100,
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelColor: INK,
    dataLabelFontSize: 11,
    dataLabelFontBold: true,
    dataLabelFormatCode: "#,##0;-#,##0",
    catAxisLabelColor: MUTED,
    catAxisLabelFontSize: 10,
    valAxisHidden: true,
    valGridLine: { style: "none" },
    catGridLine: { style: "none" },
    showLegend: false,
    showTitle: false,
    valAxisMinVal: -25000,
    valAxisMaxVal: 95000,
  });

  // how strip
  s.addShape("roundRect", {
    x: 0.55, y: 5.6, w: 12.23, h: 1.1, rectRadius: 0.07,
    fill: { color: DARK }, line: { type: "none" },
  });
  s.addText([
    { text: "어떻게: ", options: { bold: true, color: AMBER } },
    { text: "10단계 물리선별 일관 라인 — 습식 어트리션 + REFLUX™ 중력선별 + 부유선별로 은 정광 26.7% 산출. ", options: { color: "FFFFFF" } },
    { text: "화학약품·화학폐액 제로", options: { bold: true, color: AMBER } },
    { text: ", 물질 유가화율 95%+ (한국 상세설계 24개 장 · 전문가 9팀 검토 완료)", options: { color: "FFFFFF" } },
  ], {
    x: 0.9, y: 5.72, w: 11.5, h: 0.86, fontFace: FONT, fontSize: 12.5,
    lineSpacing: 20, margin: 0, valign: "middle",
  });

  footer(s, 3);
}

// ============================================================
// SLIDE 4 — ECONOMICS
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "03 · 경제성", "게이트피 없이 EBITDA $8.71M — 하방까지 검증");

  statCard(s, 0.55, 1.75, 2.95, 1.65, "$12.25M", "총 투자 (CAPEX)\n한국 검증설계 대비 12% 절감", DARK);
  statCard(s, 3.64, 1.75, 2.95, 1.65, "$8.71M", "연 EBITDA (기본 시나리오)\n마진 84% · OPEX 한국의 60%");
  statCard(s, 6.73, 1.75, 2.95, 1.65, "1.4 년", "투자 회수기간\n(가동 후 BEP 약 2.0년)");
  statCard(s, 9.82, 1.75, 2.96, 1.65, "+$26.4M", "5년 누적 FCF\n(기본 시나리오)");

  // downside verification
  s.addShape("roundRect", {
    x: 0.55, y: 3.75, w: 7.4, h: 2.9, rectRadius: 0.07,
    fill: { color: CARD }, line: { color: BORDER, width: 1 },
  });
  s.addText("하방 검증 — 어떤 가정에서도 흑자", {
    x: 0.85, y: 3.95, w: 6.8, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  const down = [
    ["은값 반토막", "$59.8 → $30/oz에도 3개 시나리오 전부 흑자 (B: $8.71M → $5.8M)"],
    ["피드스톡 최악", "폐패널을 돈 주고 사오는 바이백(C)에도 흑자 — 회수 2.1년"],
    ["보수 원칙", "EPR·게이트피·보조금 수익 $0 계상 — 규제는 상방 옵션 (+$0.9~6.1M)"],
  ];
  down.forEach((d, i) => {
    const y = 4.42 + i * 0.72;
    s.addShape("ellipse", { x: 0.9, y: y + 0.03, w: 0.3, h: 0.3, fill: { color: TINT }, line: { type: "none" } });
    s.addText("✓", {
      x: 0.9, y: y + 0.03, w: 0.3, h: 0.3, fontFace: FONT, fontSize: 12, bold: true, color: GREEN,
      align: "center", valign: "middle", margin: 0,
    });
    s.addText([
      { text: d[0] + "  ", options: { bold: true, color: INK } },
      { text: d[1], options: { color: MUTED } },
    ], {
      x: 1.35, y, w: 6.4, h: 0.66, fontFace: FONT, fontSize: 12, lineSpacing: 17, margin: 0, valign: "top",
    });
  });

  // revenue mix
  s.addShape("roundRect", {
    x: 8.15, y: 3.75, w: 4.63, h: 2.9, rectRadius: 0.07,
    fill: { color: TINT }, line: { type: "none" },
  });
  s.addText("수익 구조 — 연 소재매출 $10.41M", {
    x: 8.45, y: 3.95, w: 4.05, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  const mix = [
    ["은 정광", 56, AMBER],
    ["알루미늄", 20, GREEN],
    ["구리", 16, GREEN_LT],
    ["기타", 8, "A8C5B4"],
  ];
  mix.forEach((m, i) => {
    const y = 4.42 + i * 0.44;
    s.addText(m[0], {
      x: 8.45, y, w: 1.15, h: 0.3, fontFace: FONT, fontSize: 11, bold: true, color: INK, margin: 0, valign: "middle",
    });
    s.addShape("roundRect", {
      x: 9.65, y: y + 0.05, w: Math.max(2.3 * m[1] / 56, 0.07), h: 0.2, rectRadius: 0.02,
      fill: { color: m[2] }, line: { type: "none" },
    });
    s.addText(`${m[1]}%`, {
      x: 12.05, y, w: 0.6, h: 0.3, fontFace: FONT, fontSize: 10.5, bold: true, color: INK, margin: 0, valign: "middle", align: "right",
    });
  });
  s.addText("투입량 0.15%의 은 정광이 매출 56% — 선물 헤지(생산 50%)·오프테이크로 관리", {
    x: 8.45, y: 6.22, w: 4.05, h: 0.4, fontFace: FONT, fontSize: 9.5, color: MUTED, lineSpacing: 13, margin: 0, valign: "top",
  });

  footer(s, 4);
}

// ============================================================
// SLIDE 5 — THE ASK
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "04 · 투자 요청", "$15M — 마일스톤 연동 3개 트랜치");

  const tr = [
    ["Tranche 1", "$2.0M", "투자 실행 시", "파일럿 · 인도 법인 설립 · 실사 · 설계"],
    ["Tranche 2", "$5.0M", "파일럿 성공 (은 회수 ≥97%) + 오프테이크 LOI 2건", "부지 · 건축 · 장납기 설비 발주"],
    ["Tranche 3", "$8.0M", "인허가 완료 + 수거계약 1호", "설치 · 시운전 · 운전자본"],
  ];
  tr.forEach((t, i) => {
    const y = 1.8 + i * 1.18;
    s.addShape("roundRect", {
      x: 0.55, y, w: 7.9, h: 1.0, rectRadius: 0.07,
      fill: { color: i === 0 ? TINT : CARD }, line: { color: BORDER, width: 1 },
    });
    s.addText(t[0], {
      x: 0.85, y: y + 0.14, w: 1.7, h: 0.35, fontFace: FONT, fontSize: 13, bold: true, color: GREEN, margin: 0,
    });
    s.addText(t[1], {
      x: 0.85, y: y + 0.47, w: 1.7, h: 0.42, fontFace: FONT, fontSize: 20, bold: true, color: DARK, margin: 0,
    });
    s.addText([
      { text: "조건  ", options: { bold: true, color: AMBER, fontSize: 10.5 } },
      { text: t[2] + "\n", options: { color: INK } },
      { text: "용도  ", options: { bold: true, color: MUTED, fontSize: 10.5 } },
      { text: t[3], options: { color: MUTED } },
    ], {
      x: 2.75, y: y + 0.13, w: 5.5, h: 0.78, fontFace: FONT, fontSize: 11.5, lineSpacing: 18, margin: 0, valign: "middle",
    });
  });

  // execution readiness
  s.addShape("roundRect", {
    x: 8.75, y: 1.8, w: 4.03, h: 3.54, rectRadius: 0.07,
    fill: { color: DARK }, line: { type: "none" },
  });
  s.addText("실행 준비 완료", {
    x: 9.05, y: 2.02, w: 3.45, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: AMBER, margin: 0,
  });
  s.addText(
    "한국 상세설계 24개 장 · 전문가 9팀 검토\n\n" +
    "M0 파일럿 → M14 착공 → M27 상업운전\n\n" +
    "20명 소수정예 + 스마트팩토리 운영\n\n" +
    "정련처 5개 조사 완료 — M3~M9 오프테이크 LOI 목표\n\n" +
    "핵심공정(⑧~⑩)은 파일럿 검증 후 발주 — 실패 시 대안 경로 설계 반영",
    {
      x: 9.05, y: 2.45, w: 3.45, h: 2.8, fontFace: FONT, fontSize: 11.5, color: MINT,
      lineSpacing: 17, margin: 0, valign: "top",
    }
  );

  // return strip
  s.addShape("roundRect", {
    x: 0.55, y: 5.58, w: 12.23, h: 1.05, rectRadius: 0.07,
    fill: { color: TINT }, line: { type: "none" },
  });
  s.addText([
    { text: "리스크는 단계적으로 해소, 수익은 검증된 구조로  —  ", options: { bold: true, color: DARK } },
    { text: "정상가동 시 연 EBITDA $8.71M · 5년 누적 FCF +$26.4M (기본 시나리오)", options: { color: INK } },
  ], {
    x: 0.9, y: 5.7, w: 11.5, h: 0.8, fontFace: FONT, fontSize: 13.5, lineSpacing: 20, margin: 0, valign: "middle",
  });

  footer(s, 5);
}

// ============================================================
// SLIDE 6 — CLOSING (dark)
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: DARK };
  orbit(s, 1.3, 6.4, [1.0, 1.7, 2.5]);
  s.addShape("ellipse", { x: 12.42, y: 0.62, w: 0.16, h: 0.16, fill: { color: AMBER }, line: { type: "none" } });

  s.addText("DYNAMIC INDUSTRY", {
    x: 0.85, y: 0.6, w: 6, h: 0.35, fontFace: FONT, fontSize: 13, bold: true,
    color: "FFFFFF", charSpacing: 3, margin: 0,
  });

  s.addText([
    { text: "확정적 시장", options: { color: "FFFFFF" } },
    { text: "  ×  ", options: { color: GREEN_LT } },
    { text: "유일한 흑자 기술", options: { color: AMBER } },
    { text: "  ×  ", options: { color: GREEN_LT } },
    { text: "검증된 설계", options: { color: "FFFFFF" } },
  ], {
    x: 0.85, y: 1.35, w: 11.6, h: 0.85, fontFace: FONT, fontSize: 32, bold: true, margin: 0,
  });

  const pts = [
    ["①", "물량은 온다", "2030년 c-Si 570kt — 9,000t/년 설비 63기 규모"],
    ["②", "경쟁은 없다", "c-Si 상업 처리시설 0개, 기존 기술은 구조적 적자"],
    ["③", "우리만 꺼낸다", "화학공정 없는 물리선별로 은 회수 98%"],
    ["④", "하방이 검증됐다", "은값 반토막·바이백 시나리오에도 흑자"],
    ["⑤", "실행 준비 완료", "상세설계 24개 장 — 파일럿 즉시 착수 가능"],
  ];
  pts.forEach((p, i) => {
    const y = 2.55 + i * 0.71;
    s.addText(p[0], {
      x: 0.9, y, w: 0.45, h: 0.5, fontFace: FONT, fontSize: 17, bold: true, color: AMBER, margin: 0, valign: "middle",
    });
    s.addText([
      { text: p[1] + "  —  ", options: { bold: true, color: "FFFFFF" } },
      { text: p[2], options: { color: MINT } },
    ], {
      x: 1.45, y, w: 10.9, h: 0.5, fontFace: FONT, fontSize: 15.5, margin: 0, valign: "middle",
    });
  });

  s.addShape("line", { x: 0.9, y: 6.42, w: 11.5, h: 0, line: { color: DARK2, width: 1 } });
  s.addText([
    { text: "$15M 투자로 함께 만드는 순환경제 — 폐패널이 자원이 되는 인도    ", options: { bold: true, color: "FFFFFF" } },
    { text: "정명근 Co-founder · jmk4893@dynamicindustry.kr", options: { color: GREEN_LT } },
  ], {
    x: 0.9, y: 6.6, w: 11.6, h: 0.5, fontFace: FONT, fontSize: 13, margin: 0, valign: "middle",
  });
}

pres.writeFile({ fileName: "Dynamic_Industry_Elevator_Deck.pptx" }).then(() => console.log("done"));
