# Deck generator scripts

Node.js (pptxgenjs) scripts that generate the pitch decks in this repo.
Edit the text/numbers in a script, then regenerate the .pptx:

```bash
npm install pptxgenjs
node deck-scripts/build.js              # Korean 6-slide elevator deck
node deck-scripts/build_dashboard.js    # Korean one-page dashboard
node deck-scripts/build_en.js           # English 6-slide elevator deck
node deck-scripts/build_dashboard_en.js # English one-page dashboard
```

The .pptx files themselves are also fully editable in PowerPoint —
every element is a native text box, shape, or chart (no images).
