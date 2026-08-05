const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5

const DARK = "1B4D3E";
const DARK2 = "28604C";
const GREEN = "2E8B57";
const GREEN_LT = "589C78";
const MINT = "CDE8D8";
const AMBER = "F5B325";
const INK = "2D3E36";
const MUTED = "6E8478";
const TINT = "E4F2E9";
const CARD = "F7FBF8";
const BORDER = "DCE8E0";
const RED = "C0504D";
const FONT = "맑은 고딕";

const s = pres.addSlide();
s.background = { color: "FFFFFF" };

// ================= HEADER BAND (dark) =================
s.addShape("rect", { x: 0, y: 0, w: 13.333, h: 1.0, fill: { color: DARK }, line: { type: "none" } });
s.addText("DYNAMIC INDUSTRY", {
  x: 0.45, y: 0.14, w: 4, h: 0.3, fontFace: FONT, fontSize: 12, bold: true,
  color: "FFFFFF", charSpacing: 2.5, margin: 0,
});
s.addText([
  { text: "인도 태양광 패널 재활용 — 폐모듈을 ", options: { color: "FFFFFF" } },
  { text: "고품위 은광석", options: { color: AMBER } },
  { text: "으로", options: { color: "FFFFFF" } },
], {
  x: 0.45, y: 0.42, w: 9.2, h: 0.5, fontFace: FONT, fontSize: 21, bold: true, margin: 0, valign: "middle",
});
s.addText("화학공정 없는 물리선별 · 유일한 흑자 방정식", {
  x: 9.0, y: 0.16, w: 3.9, h: 0.28, fontFace: FONT, fontSize: 10, color: MINT, align: "right", margin: 0,
});
s.addText("정명근 Co-founder · jmk4893@dynamicindustry.kr · 2026.8", {
  x: 8.4, y: 0.55, w: 4.5, h: 0.28, fontFace: FONT, fontSize: 9.5, color: GREEN_LT, align: "right", margin: 0,
});

// ================= KPI TILE ROW =================
const kpis = [
  ["570 kt", "2030 인도 c-Si 폐패널", GREEN],
  ["0 개", "상업 경쟁시설", GREEN],
  ["98%", "은 회수율 · 화학공정 0", AMBER],
  ["$8.71M", "연 EBITDA · 마진 84%", GREEN],
  ["1.4 년", "투자 회수기간", GREEN],
  ["$15M", "투자 요청 · 3 트랜치", DARK],
];
kpis.forEach((k, i) => {
  const x = 0.45 + i * 2.09;
  s.addShape("roundRect", {
    x, y: 1.18, w: 1.97, h: 0.92, rectRadius: 0.06,
    fill: { color: "FFFFFF" }, line: { color: BORDER, width: 1 },
    shadow: { type: "outer", color: "1B4D3E", opacity: 0.08, blur: 5, offset: 2, angle: 90 },
  });
  s.addText(k[0], {
    x: x + 0.06, y: 1.26, w: 1.85, h: 0.4, fontFace: FONT, fontSize: 18.5, bold: true,
    color: k[2], align: "center", margin: 0,
  });
  s.addText(k[1], {
    x: x + 0.06, y: 1.7, w: 1.85, h: 0.32, fontFace: FONT, fontSize: 8.5, color: MUTED,
    align: "center", margin: 0, valign: "top",
  });
});

// ================= PANEL GEOMETRY =================
const PY = 2.28, PH = 3.14;

function panelTitle(x, w, tag, title) {
  s.addText([
    { text: tag + "  ", options: { color: AMBER, bold: true, fontSize: 9.5 } },
    { text: title, options: { color: DARK, bold: true, fontSize: 12.5 } },
  ], { x: x + 0.22, y: PY + 0.14, w: w - 0.44, h: 0.32, fontFace: FONT, margin: 0 });
}

// ---------- PANEL 1: 문제 ----------
{
  const X = 0.45, W = 4.14;
  s.addShape("roundRect", { x: X, y: PY, w: W, h: PH, rectRadius: 0.07, fill: { color: CARD }, line: { color: BORDER, width: 1 } });
  panelTitle(X, W, "01 문제", "물량은 쌓이는데 모두 적자");

  const rows = [
    ["기존 기계식 손실", "-₹10,230/t (CEEW 2025 실측)", RED],
    ["은 회수율 0%", "모듈 가치의 절반을 통째로 폐기", RED],
    ["원가 79%가 역물류", "바이백 68% + 수거·운송 11%", INK],
  ];
  rows.forEach((r, i) => {
    const y = PY + 0.56 + i * 0.52;
    s.addShape("ellipse", { x: X + 0.24, y: y + 0.07, w: 0.1, h: 0.1, fill: { color: r[2] === RED ? RED : GREEN }, line: { type: "none" } });
    s.addText([
      { text: r[0] + "  ", options: { bold: true, color: r[2] } },
      { text: r[1], options: { color: MUTED } },
    ], { x: X + 0.46, y, w: W - 0.68, h: 0.48, fontFace: FONT, fontSize: 10.5, lineSpacing: 14, margin: 0, valign: "top" });
  });

  // ore-grade callout
  s.addShape("roundRect", { x: X + 0.2, y: PY + 2.14, w: W - 0.4, h: 0.82, rectRadius: 0.05, fill: { color: TINT }, line: { type: "none" } });
  s.addText([
    { text: "반전 — 폐모듈 은 함량 ", options: { bold: true, color: DARK, fontSize: 10 } },
    { text: "300~500ppm", options: { bold: true, color: GREEN, fontSize: 13 } },
    { text: "\n1차 은광 채굴한계품위의 2~5배 · 1톤당 은 가치 약 $1,000", options: { color: INK, fontSize: 9 } },
  ], { x: X + 0.38, y: PY + 2.24, w: W - 0.76, h: 0.64, fontFace: FONT, lineSpacing: 15, margin: 0, valign: "middle" });
}

// ---------- PANEL 2: 솔루션 (unit economics bars drawn with shapes) ----------
{
  const X = 4.73, W = 4.14;
  s.addShape("roundRect", { x: X, y: PY, w: W, h: PH, rectRadius: 0.07, fill: { color: CARD }, line: { color: BORDER, width: 1 } });
  panelTitle(X, W, "02 솔루션", "물리선별 은 98% — 손익 반전 (₹/t)");

  // chart area
  const base = PY + 1.85; // baseline y
  const scale = 1.15 / 84200; // inches per rupee
  const bars = [
    ["기계식 P1", -10230, RED],
    ["화학식 P2", -12341, RED],
    ["Dynamic", 84200, GREEN],
  ];
  s.addShape("line", { x: X + 0.3, y: base, w: W - 0.6, h: 0, line: { color: "B9CCC0", width: 1 } });
  bars.forEach((b, i) => {
    const bw = 0.78;
    const bx = X + 0.5 + i * 1.18;
    const bh = Math.abs(b[1]) * scale;
    const by = b[1] > 0 ? base - bh : base;
    s.addShape("roundRect", { x: bx, y: by, w: bw, h: Math.max(bh, 0.1), rectRadius: 0.02, fill: { color: b[2] }, line: { type: "none" } });
    s.addText(b[1] > 0 ? "+" + b[1].toLocaleString() : b[1].toLocaleString(), {
      x: bx - 0.25, y: b[1] > 0 ? by - 0.3 : base + bh + 0.02, w: bw + 0.5, h: 0.26,
      fontFace: FONT, fontSize: 10.5, bold: true, color: b[2], align: "center", margin: 0,
    });
    s.addText(b[0], {
      x: bx - 0.25, y: base + 0.34, w: bw + 0.5, h: 0.24, fontFace: FONT, fontSize: 9, color: MUTED, align: "center", margin: 0,
    });
  });

  s.addShape("roundRect", { x: X + 0.2, y: PY + 2.42, w: W - 0.4, h: 0.54, rectRadius: 0.05, fill: { color: DARK }, line: { type: "none" } });
  s.addText([
    { text: "10단계 물리선별 — ", options: { color: "FFFFFF", bold: true } },
    { text: "화학약품·폐액 제로", options: { color: AMBER, bold: true } },
    { text: " · 물질 유가화율 95% 이상 · 은 정광 26.7%", options: { color: MINT } },
  ], { x: X + 0.36, y: PY + 2.46, w: W - 0.72, h: 0.46, fontFace: FONT, fontSize: 9, lineSpacing: 13, margin: 0, valign: "middle" });
}

// ---------- PANEL 3: 경제성 ----------
{
  const X = 9.01, W = 3.87;
  s.addShape("roundRect", { x: X, y: PY, w: W, h: PH, rectRadius: 0.07, fill: { color: CARD }, line: { color: BORDER, width: 1 } });
  panelTitle(X, W, "03 경제성", "하방까지 검증된 흑자");

  const checks = [
    ["은값 반토막($30/oz)에도", "3개 시나리오 전부 흑자"],
    ["바이백 최악 가정에도", "흑자 — 회수 2.1년"],
    ["EPR·게이트피 $0 계상", "규제는 상방 (+$0.9~6.1M)"],
  ];
  checks.forEach((c, i) => {
    const y = PY + 0.56 + i * 0.44;
    s.addText("✓", { x: X + 0.22, y, w: 0.25, h: 0.3, fontFace: FONT, fontSize: 11, bold: true, color: GREEN, margin: 0 });
    s.addText([
      { text: c[0] + " ", options: { bold: true, color: INK } },
      { text: c[1], options: { color: MUTED } },
    ], { x: X + 0.5, y, w: W - 0.72, h: 0.4, fontFace: FONT, fontSize: 9.5, lineSpacing: 13, margin: 0, valign: "top" });
  });

  // revenue mix mini bars
  s.addText("수익 구조 — 연 소재매출 $10.41M", {
    x: X + 0.22, y: PY + 1.94, w: W - 0.44, h: 0.26, fontFace: FONT, fontSize: 10, bold: true, color: DARK, margin: 0,
  });
  const mix = [
    ["은 정광", 56, AMBER],
    ["알루미늄", 20, GREEN],
    ["구리·기타", 24, GREEN_LT],
  ];
  mix.forEach((m, i) => {
    const y = PY + 2.26 + i * 0.28;
    s.addText(m[0], { x: X + 0.22, y, w: 0.85, h: 0.22, fontFace: FONT, fontSize: 8.5, bold: true, color: INK, margin: 0, valign: "middle" });
    s.addShape("roundRect", {
      x: X + 1.12, y: y + 0.035, w: Math.max(1.85 * m[1] / 56, 0.06), h: 0.15, rectRadius: 0.02,
      fill: { color: m[2] }, line: { type: "none" },
    });
    s.addText(m[1] + "%", { x: X + 3.1, y, w: 0.55, h: 0.22, fontFace: FONT, fontSize: 8.5, bold: true, color: INK, align: "right", margin: 0, valign: "middle" });
  });
}

// ================= BOTTOM: ASK STRIP =================
{
  const Y = 5.62, BH = 1.32;
  s.addShape("roundRect", { x: 0.45, y: Y, w: 12.43, h: BH, rectRadius: 0.07, fill: { color: DARK }, line: { type: "none" } });
  s.addText([
    { text: "04 투자\n", options: { color: AMBER, bold: true, fontSize: 10 } },
    { text: "$15M", options: { color: "FFFFFF", bold: true, fontSize: 26 } },
  ], { x: 0.75, y: Y + 0.18, w: 1.55, h: 1.0, fontFace: FONT, lineSpacing: 22, margin: 0, valign: "top" });

  const tr = [
    ["T1 · $2.0M", "투자 실행 시", "파일럿 · 법인 · 설계"],
    ["T2 · $5.0M", "파일럿 성공 + LOI 2건", "부지 · 건축 · 설비 발주"],
    ["T3 · $8.0M", "인허가 + 수거계약 1호", "설치 · 시운전 · 운전자본"],
  ];
  tr.forEach((t, i) => {
    const x = 2.5 + i * 2.72;
    s.addShape("roundRect", { x, y: Y + 0.18, w: 2.56, h: 0.96, rectRadius: 0.05, fill: { color: DARK2 }, line: { type: "none" } });
    s.addText([
      { text: t[0] + "\n", options: { bold: true, color: AMBER, fontSize: 11 } },
      { text: t[1] + "\n", options: { color: "FFFFFF", fontSize: 8.5 } },
      { text: t[2], options: { color: MINT, fontSize: 8.5 } },
    ], { x: x + 0.16, y: Y + 0.26, w: 2.26, h: 0.84, fontFace: FONT, lineSpacing: 13, margin: 0, valign: "top" });
  });

  s.addText("5년 누적 FCF", { x: 10.75, y: Y + 0.18, w: 2.0, h: 0.22, fontFace: FONT, fontSize: 9, color: MINT, margin: 0 });
  s.addText("+$26.4M", { x: 10.75, y: Y + 0.4, w: 2.0, h: 0.42, fontFace: FONT, fontSize: 20, bold: true, color: "FFFFFF", margin: 0 });
  s.addText("마일스톤 연동으로 리스크 단계 해소", { x: 10.75, y: Y + 0.86, w: 2.0, h: 0.3, fontFace: FONT, fontSize: 8, color: GREEN_LT, lineSpacing: 11, margin: 0, valign: "top" });
}

// footer
s.addText("출처: CEEW 2025 실측 · CEEW×MNRE 2024 · 당사 기술보고서(한국 상세설계 24개 장, 전문가 9팀 검토) — 상세 근거는 투자사업계획서 47p", {
  x: 0.45, y: 7.08, w: 10.5, h: 0.26, fontFace: FONT, fontSize: 8, color: MUTED, margin: 0,
});
s.addText("CONFIDENTIAL", {
  x: 11.4, y: 7.08, w: 1.48, h: 0.26, fontFace: FONT, fontSize: 8, color: MUTED, align: "right", charSpacing: 1, margin: 0,
});

pres.writeFile({ fileName: "Dynamic_Industry_One_Page_Dashboard.pptx" }).then(() => console.log("done"));
