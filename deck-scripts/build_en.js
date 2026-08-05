const pptxgen = require("pptxgenjs");
const LOGO = "image/png;base64," + require("fs").readFileSync(__dirname + "/logo.png").toString("base64");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5

// ---- Brand palette (from the original IR deck) ----
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

function footer(slide, num) {
  slide.addText("Solar Panel Recycling in India  ·  Elevator Pitch", {
    x: 0.55, y: 7.06, w: 5.5, h: 0.3, fontFace: FONT, fontSize: 9,
    color: MUTED, margin: 0, align: "left",
  });
  slide.addText(String(num), {
    x: 12.55, y: 7.06, w: 0.5, h: 0.3, fontFace: FONT, fontSize: 9,
    color: MUTED, margin: 0, align: "right",
  });
}

function header(slide, tag, title) {
  slide.addImage({ data: LOGO, x: 0.55, y: 0.25, w: 0.36, h: 0.32 });
  slide.addText("DYNAMIC INDUSTRY", {
    x: 1.02, y: 0.32, w: 4.0, h: 0.3, fontFace: FONT, fontSize: 11,
    bold: true, color: DARK, charSpacing: 2, margin: 0,
  });
  slide.addText(tag, {
    x: 8.8, y: 0.32, w: 3.95, h: 0.3, fontFace: FONT, fontSize: 10,
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

  s.addImage({ data: LOGO, x: 0.85, y: 0.74, w: 0.78, h: 0.7 });
  s.addText("DYNAMIC INDUSTRY", {
    x: 1.8, y: 0.78, w: 6, h: 0.4, fontFace: FONT, fontSize: 15, bold: true,
    color: "FFFFFF", charSpacing: 3, margin: 0,
  });
  s.addText("SOLAR PANEL RECYCLING · INDIA", {
    x: 1.8, y: 1.21, w: 6, h: 0.3, fontFace: FONT, fontSize: 10.5,
    color: GREEN_LT, charSpacing: 2, margin: 0,
  });

  s.addText([
    { text: "Waste panels aren't trash —\nthey're ", options: { color: "FFFFFF" } },
    { text: "high-grade silver ore", options: { color: AMBER } },
  ], {
    x: 0.85, y: 2.45, w: 11.9, h: 1.8, fontFace: FONT, fontSize: 38, bold: true,
    lineSpacing: 50, margin: 0, valign: "top",
  });

  s.addText(
    "Solar panel recycling in India — chemical-free physical separation recovers 98% of the silver,\ncreating the only profitable equation in a market where everyone loses money.",
    {
      x: 0.85, y: 4.55, w: 11.3, h: 1.0, fontFace: FONT, fontSize: 16,
      color: MINT, lineSpacing: 26, margin: 0, valign: "top",
    }
  );

  const hook = [
    ["570 kt", "India c-Si waste panels, 2030"],
    ["0", "commercial competing plants"],
    ["98%", "silver recovery · zero chemicals"],
    ["1.4 yrs", "investment payback"],
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

  s.addText("Myung-geun Jung, Co-founder   ·   Aug 2026   ·   For investment review only", {
    x: 0.85, y: 7.02, w: 8, h: 0.3, fontFace: FONT, fontSize: 9.5, color: GREEN_LT, margin: 0,
  });
}

// ============================================================
// SLIDE 2 — PROBLEM / MARKET
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "01 · MARKET & PROBLEM", "Volume is piling up — with nowhere to process it");

  statCard(s, 0.55, 1.75, 3.99, 1.7, "570 kt", "India c-Si waste panels by 2030\n(63 plants at 9,000 t/yr each)");
  statCard(s, 4.67, 1.75, 3.99, 1.7, "0", "commercial c-Si facilities —\nthe market is wide open");
  statCard(s, 8.79, 1.75, 3.99, 1.7, "-₹10,230/t", "per-ton loss of existing mechanical\nrecycling (CEEW 2025, measured)", RED);

  s.addShape("roundRect", {
    x: 0.55, y: 3.8, w: 7.4, h: 2.85, rectRadius: 0.07,
    fill: { color: CARD }, line: { color: BORDER, width: 1 },
  });
  s.addText("Why everyone loses money — anatomy of the deficit", {
    x: 0.85, y: 4.02, w: 6.8, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  const anat = [
    ["0% silver recovery", "mechanical lines discard half the module's value, selling only glass & aluminum", RED],
    ["79% of cost is reverse logistics", "module buy-back 68% + collection & transport 11% (CEEW P1)", INK],
    ["The bottleneck is feedstock economics", "not processing tech — without the silver, losses are inevitable", INK],
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

  s.addShape("roundRect", {
    x: 8.15, y: 3.8, w: 4.63, h: 2.85, rectRadius: 0.07,
    fill: { color: TINT }, line: { type: "none" },
  });
  s.addText("Yet this ‘waste’ carries silver at", {
    x: 8.45, y: 4.02, w: 4.05, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  s.addText([
    { text: "300–500 ppm", options: { fontSize: 30, bold: true, color: GREEN } },
    { text: "\n2–5× the cut-off grade of primary silver mines (100–150 ppm). An ore that needs no mining is piling up on the surface — ~$1,000 of contained silver per ton.", options: { fontSize: 12, color: INK } },
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
  header(s, "02 · SOLUTION", "98% silver recovery, zero chemicals — the economics flip");

  s.addShape("roundRect", {
    x: 0.55, y: 1.75, w: 5.6, h: 3.6, rectRadius: 0.07,
    fill: { color: CARD }, line: { color: BORDER, width: 1 },
  });
  s.addText("Material recovery vs. mechanical incumbents", {
    x: 0.85, y: 1.95, w: 5.1, h: 0.35, fontFace: FONT, fontSize: 13.5, bold: true, color: DARK, margin: 0,
  });
  const rec = [
    ["Silver (Ag)", 98, 0],
    ["Copper (Cu)", 98.4, 95],
    ["Glass", 99.3, 89],
    ["Aluminum", 99.6, 99],
  ];
  rec.forEach((r, i) => {
    const y = 2.42 + i * 0.68;
    s.addText(r[0], {
      x: 0.85, y, w: 1.3, h: 0.3, fontFace: FONT, fontSize: 11.5, bold: true, color: INK, margin: 0, valign: "middle",
    });
    const bw = 2.95;
    s.addShape("roundRect", {
      x: 2.25, y: y + 0.01, w: Math.max(bw * r[1] / 100, 0.05), h: 0.24, rectRadius: 0.03,
      fill: { color: GREEN }, line: { type: "none" },
    });
    s.addText(`${r[1]}%`, {
      x: 5.25, y: y - 0.02, w: 0.75, h: 0.3, fontFace: FONT, fontSize: 11, bold: true, color: GREEN, margin: 0, valign: "middle",
    });
    s.addShape("roundRect", {
      x: 2.25, y: y + 0.3, w: Math.max(bw * r[2] / 100, 0.05), h: 0.14, rectRadius: 0.02,
      fill: { color: "C9D6CE" }, line: { type: "none" },
    });
    s.addText(r[2] === 0 ? "0%" : `${r[2]}%`, {
      x: 5.25, y: y + 0.24, w: 0.75, h: 0.24, fontFace: FONT, fontSize: 9, color: MUTED, margin: 0, valign: "middle",
    });
  });

  s.addShape("roundRect", {
    x: 6.45, y: 1.75, w: 6.33, h: 3.6, rectRadius: 0.07,
    fill: { color: CARD }, line: { color: BORDER, width: 1 },
  });
  s.addText("Profit per ton (₹/t) — the only one in the black", {
    x: 6.75, y: 1.95, w: 5.8, h: 0.35, fontFace: FONT, fontSize: 13.5, bold: true, color: DARK, margin: 0,
  });
  s.addChart(pres.ChartType.bar, [
    {
      name: "Profit per ton",
      labels: ["Mechanical P1\n(CEEW)", "Chemical P2\n(CEEW)", "Dynamic\nIndustry"],
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

  s.addShape("roundRect", {
    x: 0.55, y: 5.6, w: 12.23, h: 1.1, rectRadius: 0.07,
    fill: { color: DARK }, line: { type: "none" },
  });
  s.addText([
    { text: "How: ", options: { bold: true, color: AMBER } },
    { text: "a 10-stage physical separation line — wet attrition + REFLUX™ gravity separation + flotation yields 26.7% silver concentrate. ", options: { color: "FFFFFF" } },
    { text: "Zero chemicals, zero chemical effluent", options: { bold: true, color: AMBER } },
    { text: ", 95%+ material valorization (24-chapter Korean detailed design · reviewed by 9 expert teams)", options: { color: "FFFFFF" } },
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
  header(s, "03 · ECONOMICS", "EBITDA $8.71M without gate fees — downside verified");

  statCard(s, 0.55, 1.75, 2.95, 1.65, "$12.25M", "total CAPEX — 12% below the\nverified Korean design", DARK);
  statCard(s, 3.64, 1.75, 2.95, 1.65, "$8.71M", "annual EBITDA · 84% margin\nOPEX at 60% of Korea");
  statCard(s, 6.73, 1.75, 2.95, 1.65, "1.4 yrs", "investment payback\n(BEP ~2.0 yrs after start-up)");
  statCard(s, 9.82, 1.75, 2.96, 1.65, "+$26.4M", "5-yr cumulative FCF\n(base case)");

  s.addShape("roundRect", {
    x: 0.55, y: 3.75, w: 7.4, h: 2.9, rectRadius: 0.07,
    fill: { color: CARD }, line: { color: BORDER, width: 1 },
  });
  s.addText("Downside verified — profitable under any assumption", {
    x: 0.85, y: 3.95, w: 6.8, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: DARK, margin: 0,
  });
  const down = [
    ["Silver halved", "$59.8 → $30/oz: all 3 scenarios stay profitable (B: $8.71M → $5.8M)"],
    ["Worst-case feedstock", "profitable even paying to buy back panels (C) — 2.1-yr payback"],
    ["Conservative principle", "$0 booked for EPR, gate fees, subsidies — regulation is pure upside (+$0.9–6.1M)"],
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

  s.addShape("roundRect", {
    x: 8.15, y: 3.75, w: 4.63, h: 2.9, rectRadius: 0.07,
    fill: { color: TINT }, line: { type: "none" },
  });
  s.addText("Revenue mix — $10.41M annual sales", {
    x: 8.45, y: 3.95, w: 4.05, h: 0.35, fontFace: FONT, fontSize: 13.5, bold: true, color: DARK, margin: 0,
  });
  const mix = [
    ["Silver conc.", 56, AMBER],
    ["Aluminum", 20, GREEN],
    ["Copper", 16, GREEN_LT],
    ["Other", 8, "A8C5B4"],
  ];
  mix.forEach((m, i) => {
    const y = 4.42 + i * 0.44;
    s.addText(m[0], {
      x: 8.45, y, w: 1.2, h: 0.3, fontFace: FONT, fontSize: 10.5, bold: true, color: INK, margin: 0, valign: "middle",
    });
    s.addShape("roundRect", {
      x: 9.7, y: y + 0.05, w: Math.max(2.25 * m[1] / 56, 0.07), h: 0.2, rectRadius: 0.02,
      fill: { color: m[2] }, line: { type: "none" },
    });
    s.addText(`${m[1]}%`, {
      x: 12.05, y, w: 0.6, h: 0.3, fontFace: FONT, fontSize: 10.5, bold: true, color: INK, margin: 0, valign: "middle", align: "right",
    });
  });
  s.addText("0.15% of input mass = 56% of revenue — managed via futures hedge (50% of output) & offtake", {
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
  header(s, "04 · THE ASK", "$15M — three milestone-linked tranches");

  const tr = [
    ["Tranche 1", "$2.0M", "On closing", "Pilot · India entity · due diligence · design"],
    ["Tranche 2", "$5.0M", "Pilot success (Ag recovery ≥97%) + 2 offtake LOIs", "Site · construction · long-lead equipment"],
    ["Tranche 3", "$8.0M", "Permits complete + first collection contract", "Installation · commissioning · working capital"],
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
      { text: "Gate  ", options: { bold: true, color: AMBER, fontSize: 10.5 } },
      { text: t[2] + "\n", options: { color: INK } },
      { text: "Use  ", options: { bold: true, color: MUTED, fontSize: 10.5 } },
      { text: t[3], options: { color: MUTED } },
    ], {
      x: 2.75, y: y + 0.13, w: 5.5, h: 0.78, fontFace: FONT, fontSize: 11.5, lineSpacing: 18, margin: 0, valign: "middle",
    });
  });

  s.addShape("roundRect", {
    x: 8.75, y: 1.8, w: 4.03, h: 3.54, rectRadius: 0.07,
    fill: { color: DARK }, line: { type: "none" },
  });
  s.addText("Ready to execute", {
    x: 9.05, y: 2.02, w: 3.45, h: 0.35, fontFace: FONT, fontSize: 14, bold: true, color: AMBER, margin: 0,
  });
  s.addText(
    "24-chapter Korean detailed design, 9 expert-team review\n\n" +
    "M0 pilot → M14 build → M27 commercial operation\n\n" +
    "20-person lean team + smart factory\n\n" +
    "5 refiners surveyed — offtake LOIs by M3–M9\n\n" +
    "Core stages ordered after pilot — fallback designed in",
    {
      x: 9.05, y: 2.45, w: 3.45, h: 2.8, fontFace: FONT, fontSize: 10.5, color: MINT,
      lineSpacing: 15, margin: 0, valign: "top",
    }
  );

  s.addShape("roundRect", {
    x: 0.55, y: 5.58, w: 12.23, h: 1.05, rectRadius: 0.07,
    fill: { color: TINT }, line: { type: "none" },
  });
  s.addText([
    { text: "Risk retired in stages, returns on a verified structure  —  ", options: { bold: true, color: DARK } },
    { text: "at full operation: $8.71M annual EBITDA · +$26.4M 5-yr cumulative FCF (base case)", options: { color: INK } },
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

  s.addImage({ data: LOGO, x: 0.85, y: 0.53, w: 0.47, h: 0.42 });
  s.addText("DYNAMIC INDUSTRY", {
    x: 1.47, y: 0.57, w: 6, h: 0.35, fontFace: FONT, fontSize: 13, bold: true,
    color: "FFFFFF", charSpacing: 3, margin: 0, valign: "middle",
  });

  s.addText([
    { text: "Certain market", options: { color: "FFFFFF" } },
    { text: " × ", options: { color: GREEN_LT } },
    { text: "only profitable tech", options: { color: AMBER } },
    { text: " × ", options: { color: GREEN_LT } },
    { text: "verified design", options: { color: "FFFFFF" } },
  ], {
    x: 0.85, y: 1.35, w: 12.0, h: 0.85, fontFace: FONT, fontSize: 26, bold: true, margin: 0, valign: "middle",
  });

  const pts = [
    ["①", "The volume is coming", "570 kt of c-Si by 2030 — enough for 63 plants at 9,000 t/yr"],
    ["②", "There is no competition", "zero commercial c-Si facilities; incumbents lose money structurally"],
    ["③", "Only we extract the silver", "98% recovery via chemical-free physical separation"],
    ["④", "The downside is verified", "profitable even with silver halved or panel buy-back"],
    ["⑤", "Ready to execute", "24-chapter detailed design — pilot can start immediately"],
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
  s.addText("$15M to make waste panels a resource — India's circular economy", {
    x: 0.9, y: 6.6, w: 6.9, h: 0.5, fontFace: FONT, fontSize: 12, bold: true, color: "FFFFFF", margin: 0, valign: "middle",
  });
  s.addText("Myung-geun Jung, Co-founder · jmk4893@dynamicindustry.kr", {
    x: 7.8, y: 6.6, w: 4.7, h: 0.5, fontFace: FONT, fontSize: 10.5, color: GREEN_LT, align: "right", margin: 0, valign: "middle",
  });
}

pres.writeFile({ fileName: "Dynamic_Industry_Elevator_Deck_EN.pptx" }).then(() => console.log("done"));
