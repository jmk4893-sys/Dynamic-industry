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
const FONT = "Calibri";

const s = pres.addSlide();
s.background = { color: "FFFFFF" };

// ================= HEADER BAND (dark) =================
s.addShape("rect", { x: 0, y: 0, w: 13.333, h: 1.0, fill: { color: DARK }, line: { type: "none" } });
s.addText("DYNAMIC INDUSTRY", {
  x: 0.45, y: 0.14, w: 4, h: 0.3, fontFace: FONT, fontSize: 12, bold: true,
  color: "FFFFFF", charSpacing: 2.5, margin: 0,
});
s.addText([
  { text: "Solar Panel Recycling in India — modules as ", options: { color: "FFFFFF" } },
  { text: "high-grade silver ore", options: { color: AMBER } },
], {
  x: 0.45, y: 0.42, w: 8.5, h: 0.5, fontFace: FONT, fontSize: 15, bold: true, margin: 0, valign: "middle",
});
s.addText("Chemical-free separation · the only profitable equation", {
  x: 9.0, y: 0.16, w: 3.9, h: 0.28, fontFace: FONT, fontSize: 9.5, color: MINT, align: "right", margin: 0,
});
s.addText("Myung-geun Jung · jmk4893@dynamicindustry.kr · Aug 2026", {
  x: 9.0, y: 0.55, w: 3.9, h: 0.28, fontFace: FONT, fontSize: 9, color: GREEN_LT, align: "right", margin: 0,
});

// ================= KPI TILE ROW =================
const kpis = [
  ["570 kt", "India c-Si waste, 2030", GREEN],
  ["0", "commercial competitors", GREEN],
  ["98%", "Ag recovery · 0 chemicals", AMBER],
  ["$8.71M", "annual EBITDA · 84% margin", GREEN],
  ["1.4 yrs", "investment payback", GREEN],
  ["$15M", "the ask · 3 tranches", DARK],
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

// ---------- PANEL 1: PROBLEM ----------
{
  const X = 0.45, W = 4.14;
  s.addShape("roundRect", { x: X, y: PY, w: W, h: PH, rectRadius: 0.07, fill: { color: CARD }, line: { color: BORDER, width: 1 } });
  panelTitle(X, W, "01 PROBLEM", "Volume up, everyone loses");

  const rows = [
    ["Mechanical loss", "-₹10,230/t (CEEW 2025, measured)", RED],
    ["0% silver recovery", "half the module's value discarded", RED],
    ["79% reverse logistics", "buy-back 68% + collection 11%", INK],
  ];
  rows.forEach((r, i) => {
    const y = PY + 0.56 + i * 0.52;
    s.addShape("ellipse", { x: X + 0.24, y: y + 0.07, w: 0.1, h: 0.1, fill: { color: r[2] === RED ? RED : GREEN }, line: { type: "none" } });
    s.addText([
      { text: r[0] + "  ", options: { bold: true, color: r[2] } },
      { text: r[1], options: { color: MUTED } },
    ], { x: X + 0.46, y, w: W - 0.68, h: 0.48, fontFace: FONT, fontSize: 10.5, lineSpacing: 14, margin: 0, valign: "top" });
  });

  s.addShape("roundRect", { x: X + 0.2, y: PY + 2.14, w: W - 0.4, h: 0.82, rectRadius: 0.05, fill: { color: TINT }, line: { type: "none" } });
  s.addText([
    { text: "The twist — modules carry ", options: { bold: true, color: DARK, fontSize: 10 } },
    { text: "300–500 ppm Ag", options: { bold: true, color: GREEN, fontSize: 13 } },
    { text: "\n2–5× mine cut-off grade · ~$1,000 of silver per ton", options: { color: INK, fontSize: 9 } },
  ], { x: X + 0.38, y: PY + 2.24, w: W - 0.76, h: 0.64, fontFace: FONT, lineSpacing: 15, margin: 0, valign: "middle" });
}

// ---------- PANEL 2: SOLUTION ----------
{
  const X = 4.73, W = 4.14;
  s.addShape("roundRect", { x: X, y: PY, w: W, h: PH, rectRadius: 0.07, fill: { color: CARD }, line: { color: BORDER, width: 1 } });
  panelTitle(X, W, "02 SOLUTION", "Ag 98% — profit flips (₹/t)");

  const base = PY + 1.85;
  const scale = 1.15 / 84200;
  const bars = [
    ["Mechanical P1", -10230, RED],
    ["Chemical P2", -12341, RED],
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
    { text: "10-stage physical line — ", options: { color: "FFFFFF", bold: true } },
    { text: "zero chemicals & effluent", options: { color: AMBER, bold: true } },
    { text: " · 95%+ valorization · 26.7% Ag concentrate", options: { color: MINT } },
  ], { x: X + 0.36, y: PY + 2.46, w: W - 0.72, h: 0.46, fontFace: FONT, fontSize: 9, lineSpacing: 13, margin: 0, valign: "middle" });
}

// ---------- PANEL 3: ECONOMICS ----------
{
  const X = 9.01, W = 3.87;
  s.addShape("roundRect", { x: X, y: PY, w: W, h: PH, rectRadius: 0.07, fill: { color: CARD }, line: { color: BORDER, width: 1 } });
  panelTitle(X, W, "03 ECONOMICS", "Profitable at the downside");

  const checks = [
    ["Silver halved ($30/oz):", "all 3 scenarios profitable"],
    ["Worst-case buy-back:", "still profitable — 2.1-yr payback"],
    ["EPR & gate fees at $0:", "regulation is upside (+$0.9–6.1M)"],
  ];
  checks.forEach((c, i) => {
    const y = PY + 0.56 + i * 0.44;
    s.addText("✓", { x: X + 0.22, y, w: 0.25, h: 0.3, fontFace: FONT, fontSize: 11, bold: true, color: GREEN, margin: 0 });
    s.addText([
      { text: c[0] + " ", options: { bold: true, color: INK } },
      { text: c[1], options: { color: MUTED } },
    ], { x: X + 0.5, y, w: W - 0.72, h: 0.4, fontFace: FONT, fontSize: 9.5, lineSpacing: 13, margin: 0, valign: "top" });
  });

  s.addText("Revenue mix — $10.41M annual sales", {
    x: X + 0.22, y: PY + 1.94, w: W - 0.44, h: 0.26, fontFace: FONT, fontSize: 10, bold: true, color: DARK, margin: 0,
  });
  const mix = [
    ["Silver conc.", 56, AMBER],
    ["Aluminum", 20, GREEN],
    ["Cu & other", 24, GREEN_LT],
  ];
  mix.forEach((m, i) => {
    const y = PY + 2.26 + i * 0.28;
    s.addText(m[0], { x: X + 0.22, y, w: 0.95, h: 0.22, fontFace: FONT, fontSize: 8.5, bold: true, color: INK, margin: 0, valign: "middle" });
    s.addShape("roundRect", {
      x: X + 1.22, y: y + 0.035, w: Math.max(1.75 * m[1] / 56, 0.06), h: 0.15, rectRadius: 0.02,
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
    { text: "04 THE ASK\n", options: { color: AMBER, bold: true, fontSize: 10 } },
    { text: "$15M", options: { color: "FFFFFF", bold: true, fontSize: 26 } },
  ], { x: 0.75, y: Y + 0.18, w: 1.6, h: 1.0, fontFace: FONT, lineSpacing: 22, margin: 0, valign: "top" });

  const tr = [
    ["T1 · $2.0M", "On closing", "Pilot · entity · design"],
    ["T2 · $5.0M", "Pilot success + 2 LOIs", "Site · construction · equipment"],
    ["T3 · $8.0M", "Permits + collection deal", "Install · commissioning · WC"],
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

  s.addText("5-yr cumulative FCF", { x: 10.75, y: Y + 0.18, w: 2.0, h: 0.22, fontFace: FONT, fontSize: 9, color: MINT, margin: 0 });
  s.addText("+$26.4M", { x: 10.75, y: Y + 0.4, w: 2.0, h: 0.42, fontFace: FONT, fontSize: 20, bold: true, color: "FFFFFF", margin: 0 });
  s.addText("milestones retire risk in stages", { x: 10.75, y: Y + 0.86, w: 2.0, h: 0.3, fontFace: FONT, fontSize: 8, color: GREEN_LT, lineSpacing: 11, margin: 0, valign: "top" });
}

// footer
s.addText("Sources: CEEW 2025 (measured) · CEEW×MNRE 2024 · company technical report (24-chapter Korean detailed design, 9 expert-team review) — full basis in the 47-page business plan", {
  x: 0.45, y: 7.08, w: 11.2, h: 0.26, fontFace: FONT, fontSize: 8, color: MUTED, margin: 0,
});
s.addText("CONFIDENTIAL", {
  x: 11.7, y: 7.08, w: 1.18, h: 0.26, fontFace: FONT, fontSize: 8, color: MUTED, align: "right", charSpacing: 1, margin: 0,
});

pres.writeFile({ fileName: "Dynamic_Industry_One_Page_Dashboard_EN.pptx" }).then(() => console.log("done"));
