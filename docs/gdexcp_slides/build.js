const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const Fa = require("react-icons/fa");

// ---- palette: Ocean Gradient ----
const DEEP = "065A82";   // deep blue (primary)
const TEAL = "1C7293";   // teal (secondary)
const MID  = "21295C";   // midnight (accent / dark bg)
const ICE  = "CADCFC";   // light tint
const WHITE = "FFFFFF";
const INK  = "1B2430";   // body text
const MUTE = "5B6B7B";   // muted text
const CARD = "F3F7FA";   // card fill
const CODEBG = "11203A";  // code block bg
const CODEFG = "D6E6F5";  // code text
const ACCENT = "23B5A8";  // mint accent for code keywords / highlights

const HFONT = "Trebuchet MS";
const BFONT = "Calibri";
const MONO = "Consolas";

async function png(IconComponent, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color, size: String(size) })
  );
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const shadow = () => ({ type: "outer", color: "000000", blur: 7, offset: 3, angle: 90, opacity: 0.12 });

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
  pres.author = "NSF NCAR / RDA";
  pres.title = "gdexcp";
  const W = 13.3, H = 7.5;

  // preload icons
  const ic = {
    copy: await png(Fa.FaCopy, "#" + WHITE),
    folder: await png(Fa.FaFolderOpen, "#" + DEEP),
    server: await png(Fa.FaServer, "#" + DEEP),
    cloud: await png(Fa.FaCloud, "#" + DEEP),
    globe: await png(Fa.FaGlobe, "#" + DEEP),
    bolt: await png(Fa.FaBolt, "#" + DEEP),
    layer: await png(Fa.FaLayerGroup, "#" + DEEP),
    clock: await png(Fa.FaClock, "#" + DEEP),
    lock: await png(Fa.FaLock, "#" + DEEP),
    user: await png(Fa.FaUserShield, "#" + DEEP),
    list: await png(Fa.FaListUl, "#" + DEEP),
    check: await png(Fa.FaCheckCircle, "#" + ACCENT),
    warn: await png(Fa.FaExclamationTriangle, "#" + "E08A1E"),
    arrow: await png(Fa.FaArrowRight, "#" + TEAL),
    term: await png(Fa.FaTerminal, "#" + ACCENT),
    cogs: await png(Fa.FaCogs, "#" + DEEP),
  };

  // ---------- helpers ----------
  function sectionTitle(slide, txt, kicker) {
    slide.addText(txt, { x: 0.7, y: 0.45, w: 12, h: 0.7, fontFace: HFONT, fontSize: 30, bold: true, color: MID });
    if (kicker) slide.addText(kicker.toUpperCase(), { x: 0.72, y: 0.18, w: 12, h: 0.3, fontFace: HFONT, fontSize: 12, bold: true, color: TEAL, charSpacing: 3 });
  }

  function codeBox(slide, lines, x, y, w, h, fs = 13) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: CODEBG }, rectRadius: 0.06, line: { type: "none" }, shadow: shadow() });
    const runs = [];
    lines.forEach((ln, i) => {
      runs.push({ text: ln, options: { color: CODEFG, breakLine: i < lines.length - 1 } });
    });
    slide.addText(runs, { x: x + 0.22, y: y + 0.12, w: w - 0.4, h: h - 0.24, fontFace: MONO, fontSize: fs, color: CODEFG, valign: "top", align: "left", lineSpacingMultiple: 1.18 });
  }

  // card with icon, header, body
  function featureCard(slide, x, y, w, h, icon, header, body) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: CARD }, rectRadius: 0.08, line: { type: "none" }, shadow: shadow() });
    slide.addShape(pres.shapes.OVAL, { x: x + 0.28, y: y + 0.28, w: 0.62, h: 0.62, fill: { color: ICE }, line: { type: "none" } });
    slide.addImage({ data: icon, x: x + 0.42, y: y + 0.42, w: 0.34, h: 0.34 });
    slide.addText(header, { x: x + 1.05, y: y + 0.26, w: w - 1.25, h: 0.6, fontFace: HFONT, fontSize: 16, bold: true, color: MID, valign: "middle", margin: 0 });
    slide.addText(body, { x: x + 0.32, y: y + 1.0, w: w - 0.6, h: h - 1.15, fontFace: BFONT, fontSize: 12.5, color: INK, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
  }

  // =========================================================
  // SLIDE 1 — TITLE
  // =========================================================
  let s = pres.addSlide();
  s.background = { color: MID };
  s.addShape(pres.shapes.OVAL, { x: 9.6, y: -2.2, w: 6.5, h: 6.5, fill: { color: DEEP }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: 11.2, y: 3.6, w: 4.2, h: 4.2, fill: { color: TEAL }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: 1.1, y: 1.55, w: 1.35, h: 1.35, fill: { color: TEAL }, line: { type: "none" } });
  s.addImage({ data: ic.copy, x: 1.42, y: 1.86, w: 0.73, h: 0.73 });
  s.addText("gdexcp", { x: 1.0, y: 3.05, w: 9, h: 1.1, fontFace: HFONT, fontSize: 60, bold: true, color: WHITE, margin: 0 });
  s.addText("Copy files & directories as user 'gdexdata'", { x: 1.04, y: 4.15, w: 10, h: 0.6, fontFace: HFONT, fontSize: 22, color: ICE, margin: 0 });
  s.addText("Local hosts | Remote hosts | Object Store buckets | Globus endpoints", { x: 1.04, y: 4.85, w: 11, h: 0.4, fontFace: BFONT, fontSize: 14, italic: true, color: "9DB6D6", margin: 0 });
  s.addText("NSF NCAR  ·  Research Data Archive (RDA / GDEX)", { x: 1.04, y: 6.6, w: 10, h: 0.4, fontFace: BFONT, fontSize: 12, color: "7E94B8", margin: 0, charSpacing: 1 });

  // =========================================================
  // SLIDE 2 — WHAT IT DOES / OVERVIEW
  // =========================================================
  s = pres.addSlide();
  s.background = { color: WHITE };
  sectionTitle(s, "What gdexcp does", "Overview");
  s.addText("A single command-line copy tool for the data archive. Source and target may each live on a local host, a remote host, an Object Store bucket, or a Globus endpoint. Target files are written owned by 'gdexdata' with configurable permissions.", { x: 0.7, y: 1.25, w: 12, h: 0.9, fontFace: BFONT, fontSize: 15, color: INK, lineSpacingMultiple: 1.1 });

  const ovCards = [
    [ic.user, "Runs as 'gdexdata'", "Setuid tool. Targets are owned by the common archive user with modes you set (-F / -D)."],
    [ic.globe, "Any source ↔ any target", "Local, remote host, Object Store bucket, or Globus endpoint — in any combination."],
    [ic.bolt, "Parallel & scalable", "Copy many files at once with -m, or queue a delayed PBS batch job with -d."],
  ];
  let cx = 0.7; const cw = 3.97, gap = 0.2;
  ovCards.forEach((c) => { featureCard(s, cx, 2.35, cw, 2.35, c[0], c[1], c[2]); cx += cw + gap; });

  codeBox(s, ["$ gdexcp -r -f *  -t /PathTo/d277006/  -th castle"], 0.7, 5.05, 12, 0.62, 15);
  s.addText("Run from any directory. With no source paths, gdexcp prints its usage.", { x: 0.7, y: 5.8, w: 12, h: 0.4, fontFace: BFONT, fontSize: 12.5, italic: true, color: MUTE });

  // =========================================================
  // SLIDE 3 — SOURCE & TARGET
  // =========================================================
  s = pres.addSlide();
  s.background = { color: WHITE };
  sectionTitle(s, "Specifying source and target", "Core options");

  featureCard(s, 0.7, 1.4, 5.95, 1.75, ic.folder, "-f   From directories / files", "Default option — paths may be given with no flag. Shell wildcards work; use ./ or * for everything here. A trailing / copies a directory's contents as a list rather than the directory itself.");
  featureCard(s, 6.85, 1.4, 5.75, 1.75, ic.list, "-i   Input file", "A file listing source paths, one per line. Blank lines and lines starting with # are ignored. Read paths are appended to the -f list.");
  featureCard(s, 0.7, 3.35, 5.95, 1.5, ic.arrow, "-t   To directory / file name", "Target directory or file. Defaults to '.'. A trailing / forces directory treatment. Multiple sources cannot go to one target file name.");

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.85, y: 3.35, w: 5.75, h: 1.5, fill: { color: CARD }, rectRadius: 0.08, line: { type: "none" }, shadow: shadow() });
  s.addText("Trailing-slash rule", { x: 7.1, y: 3.5, w: 5.3, h: 0.35, fontFace: HFONT, fontSize: 14, bold: true, color: MID, margin: 0 });
  s.addText([
    { text: "DirName/", options: { fontFace: MONO, color: ACCENT } },
    { text: "  copies the contents only", options: { color: INK } },
  ], { x: 7.1, y: 3.9, w: 5.3, h: 0.35, fontSize: 12.5, fontFace: BFONT, margin: 0 });
  s.addText([
    { text: "DirName", options: { fontFace: MONO, color: ACCENT } },
    { text: "   copies the directory itself too", options: { color: INK } },
  ], { x: 7.1, y: 4.28, w: 5.3, h: 0.35, fontSize: 12.5, fontFace: BFONT, margin: 0 });

  codeBox(s, ["$ gdexcp -i filelist.txt -t /PathTo/d277006/"], 0.7, 5.15, 12, 0.6, 15);

  // =========================================================
  // SLIDE 4 — LOCATIONS
  // =========================================================
  s = pres.addSlide();
  s.background = { color: WHITE };
  sectionTitle(s, "Source / target locations", "Where the data lives");
  s.addText("Default is the local host. Add a 'from' (-f*) and/or 'to' (-t*) location flag to copy across hosts, buckets, or endpoints.", { x: 0.7, y: 1.2, w: 12, h: 0.5, fontFace: BFONT, fontSize: 14, color: INK });

  const loc = [
    [ic.server, "Remote host", "-fh FromHostName", "-th ToHostName"],
    [ic.cloud, "Object Store bucket", "-fb FromBucket", "-tb ToBucket"],
    [ic.globe, "Globus endpoint", "-fp FromEndpoint", "-tp ToEndpoint"],
  ];
  cx = 0.7;
  loc.forEach((l) => {
    const x = cx, y = 2.0, w = 3.97, h = 2.5;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: CARD }, rectRadius: 0.08, line: { type: "none" }, shadow: shadow() });
    s.addShape(pres.shapes.OVAL, { x: x + w / 2 - 0.42, y: y + 0.3, w: 0.84, h: 0.84, fill: { color: ICE }, line: { type: "none" } });
    s.addImage({ data: l[0], x: x + w / 2 - 0.23, y: y + 0.51, w: 0.46, h: 0.46 });
    s.addText(l[1], { x, y: y + 1.25, w, h: 0.4, align: "center", fontFace: HFONT, fontSize: 16, bold: true, color: MID, margin: 0 });
    s.addText([
      { text: l[2], options: { fontFace: MONO, color: TEAL, breakLine: true } },
      { text: l[3], options: { fontFace: MONO, color: DEEP } },
    ], { x: x + 0.3, y: y + 1.7, w: w - 0.6, h: 0.6, align: "center", fontSize: 12.5, margin: 0, lineSpacingMultiple: 1.2 });
    cx += w + gap;
  });

  s.addText([
    { text: "Tip: ", options: { bold: true, color: TEAL } },
    { text: "if a Globus endpoint is locally accessible, a direct local copy (omit -fp/-tp, give the local path) is faster — it avoids the Globus transfer overhead.", options: { color: INK } },
  ], { x: 0.7, y: 4.95, w: 12, h: 0.7, fontFace: BFONT, fontSize: 13.5, italic: true, lineSpacingMultiple: 1.1 });

  // =========================================================
  // SLIDE 5 — COPY BEHAVIOR
  // =========================================================
  s = pres.addSlide();
  s.background = { color: WHITE };
  sectionTitle(s, "Controlling the copy", "Copy behavior");

  const beh = [
    [ic.layer, "-r  /  -R level", "Recurse with no limit (-r), or up to a given depth (-R). -R 1 copies only the immediate contents."],
    [ic.check, "-O  override", "By default a target with the same size is skipped. -O copies anyway and overwrites the existing target."],
    [ic.user, "-o  force owner", "Force a downloaded file to be owned by 'gdexdata' (requires -fp; download-to-local only)."],
  ];
  cx = 0.7;
  beh.forEach((c) => { featureCard(s, cx, 1.35, cw, 2.0, c[0], c[1], c[2]); cx += cw + gap; });

  // same-size skip flow
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 3.65, w: 12, h: 1.05, fill: { color: MID }, rectRadius: 0.08, line: { type: "none" } });
  s.addText("Same-size skip", { x: 0.95, y: 3.78, w: 3, h: 0.4, fontFace: HFONT, fontSize: 14, bold: true, color: ICE, margin: 0 });
  s.addText([
    { text: "Target missing or different size", options: { color: WHITE } },
    { text: "  →  copy   ", options: { color: ACCENT, bold: true } },
    { text: "|   Same size", options: { color: WHITE } },
    { text: "  →  skip   ", options: { color: "F0B65A", bold: true } },
    { text: "|   add ", options: { color: WHITE } },
    { text: "-O", options: { fontFace: MONO, color: ACCENT } },
    { text: "  →  always overwrite", options: { color: WHITE } },
  ], { x: 0.95, y: 4.18, w: 11.6, h: 0.45, fontFace: BFONT, fontSize: 13.5, margin: 0 });

  codeBox(s, ["$ gdexcp -r -f /PathTo/DirectoryName/ -t /PathTo/d277006/ -th castle"], 0.7, 5.05, 12, 0.6, 14);

  // =========================================================
  // SLIDE 6 — PARALLEL & DELAYED BATCH
  // =========================================================
  s = pres.addSlide();
  s.background = { color: WHITE };
  sectionTitle(s, "Going parallel & running later", "Scale: -m and -d");

  featureCard(s, 0.7, 1.4, 5.95, 2.2, ic.bolt, "-m  ProcessCount  (default 1)",
    "Copy files in parallel across that many child processes. The source list is distributed across the workers automatically. Capped at 16 — a larger value is reduced to 16 with a warning.");
  featureCard(s, 6.85, 1.4, 5.75, 2.2, ic.clock, "-d  delayed PBS batch job",
    "Queue this command as a dscheck record; the dscheck daemon submits it later to PBS via bashqsub / tcshqsub. The actual copy then runs unattended.");

  // PBS resource callout
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 3.8, w: 12, h: 1.35, fill: { color: CARD }, rectRadius: 0.08, line: { type: "none" }, shadow: shadow() });
  s.addImage({ data: ic.cogs, x: 1.0, y: 4.1, w: 0.5, h: 0.5 });
  s.addText("PBS resources reserved by -d", { x: 1.65, y: 3.98, w: 10.7, h: 0.4, fontFace: HFONT, fontSize: 15, bold: true, color: MID, margin: 0 });
  s.addText([
    { text: "Always: ", options: { bold: true, color: TEAL } },
    { text: "24-hour walltime.", options: { color: INK } },
    { text: "   With -m N (>1): ", options: { bold: true, color: TEAL } },
    { text: "one node, N cpus, 1 GB memory per cpu.", options: { color: INK } },
  ], { x: 1.65, y: 4.42, w: 10.8, h: 0.4, fontFace: BFONT, fontSize: 13.5, margin: 0 });
  s.addText([{ text: "-l walltime=24:00:00,select=1:ncpus=N:mem=Ngb", options: { fontFace: MONO, color: ACCENT } }],
    { x: 1.65, y: 4.78, w: 10.8, h: 0.35, fontSize: 12.5, margin: 0 });

  s.addText([
    { text: "Warning: ", options: { bold: true, color: "C0560E" } },
    { text: "do not queue one batch job to copy too many files — if it can't finish within 24 hours the job is killed. Split very large copies into several -d jobs and/or raise -m.", options: { color: INK } },
  ], { x: 0.7, y: 5.35, w: 12, h: 0.7, fontFace: BFONT, fontSize: 13, italic: true, lineSpacingMultiple: 1.1 });

  // =========================================================
  // SLIDE 7 — PERMISSIONS & MISC
  // =========================================================
  s = pres.addSlide();
  s.background = { color: WHITE };
  sectionTitle(s, "Permissions & the rest", "Target modes · help");

  featureCard(s, 0.7, 1.5, 5.95, 1.7, ic.lock, "-F  FileMode   (default 664)", "Octal permission mode applied to target files.");
  featureCard(s, 6.85, 1.5, 5.75, 1.7, ic.folder, "-D  DirectoryMode  (default 775)", "Octal permission mode applied to target directories.");
  featureCard(s, 0.7, 3.4, 5.95, 1.5, ic.list, "-h   Help", "Display the full usage document.");
  featureCard(s, 6.85, 3.4, 5.75, 1.5, ic.user, "Readable by 'gdexdata'", "Source paths must be readable by gdexdata; gdexcp tries to fix the mode when they are not.");

  codeBox(s, ["$ gdexcp -f /PathTo/myfile.nc -tb my-bucket -t myfile.nc -F 644"], 0.7, 5.2, 12, 0.6, 14);

  // =========================================================
  // SLIDE 8 — EXAMPLES
  // =========================================================
  s = pres.addSlide();
  s.background = { color: MID };
  s.addText("EXAMPLES", { x: 0.72, y: 0.35, w: 12, h: 0.3, fontFace: HFONT, fontSize: 12, bold: true, color: ACCENT, charSpacing: 3 });
  s.addText("Common gdexcp commands", { x: 0.7, y: 0.6, w: 12, h: 0.7, fontFace: HFONT, fontSize: 28, bold: true, color: WHITE });

  const ex = [
    ["Copy everything under the cwd to a remote host", "gdexcp -r -f * -t /PathTo/d277006/ -th castle"],
    ["Copy a single file to an Object Store bucket", "gdexcp -f /PathTo/myfile.nc -tb my-bucket -t myfile.nc"],
    ["Pull files from a remote host to the local cwd", "gdexcp -fh castle -f /PathTo/d277006/myfile.nc"],
    ["Download from Globus, force 'gdexdata' ownership", "gdexcp -fp gdex-quasar -f /d277006/myfile.nc -t /PathTo/myfile.nc -o"],
    ["Copy a path list using 4 parallel processes", "gdexcp -i filelist.txt -t /PathTo/d277006/ -m 4"],
    ["Queue a delayed parallel PBS batch copy", "gdexcp -r -f /PathTo/DirectoryName/ -t /PathTo/d277006/ -m 4 -d"],
  ];
  let ey = 1.55; const eh = 0.86, ew = 12;
  ex.forEach((e, i) => {
    const x = 0.7, y = ey;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: ew, h: eh, fill: { color: CODEBG }, rectRadius: 0.05, line: { type: "none" } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.22, y: y + eh / 2 - 0.22, w: 0.44, h: 0.44, fill: { color: TEAL }, line: { type: "none" } });
    s.addText(String(i + 1), { x: x + 0.22, y: y + eh / 2 - 0.22, w: 0.44, h: 0.44, align: "center", valign: "middle", fontFace: HFONT, fontSize: 15, bold: true, color: WHITE, margin: 0 });
    s.addText(e[0], { x: x + 0.85, y: y + 0.08, w: ew - 1.1, h: 0.32, fontFace: BFONT, fontSize: 11.5, italic: true, color: "8FB8D6", margin: 0 });
    s.addText([{ text: "$ ", options: { color: ACCENT } }, { text: e[1], options: { color: CODEFG } }],
      { x: x + 0.85, y: y + 0.4, w: ew - 1.1, h: 0.38, fontFace: MONO, fontSize: 13, margin: 0 });
    ey += eh + 0.1;
  });

  // =========================================================
  // SLIDE 9 — CLOSING / KEY POINTS
  // =========================================================
  s = pres.addSlide();
  s.background = { color: DEEP };
  s.addShape(pres.shapes.OVAL, { x: -2.0, y: 4.2, w: 6, h: 6, fill: { color: MID }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: 10.8, y: -2.2, w: 5.5, h: 5.5, fill: { color: TEAL }, line: { type: "none" } });
  s.addText("Key things to remember", { x: 0.8, y: 0.7, w: 11.5, h: 0.8, fontFace: HFONT, fontSize: 30, bold: true, color: WHITE });

  const pts = [
    "Trailing / on a source copies its contents; without it the directory itself is copied too.",
    "Same-size targets are skipped by default — use -O to force an overwrite.",
    "Locally-accessible Globus endpoint? A direct local copy is faster than -fp/-tp.",
    "-m runs parallel copies (max 16); -d queues a 24-hour PBS batch job.",
    "Don't pack one -d job with too many files — split large copies so they finish in 24 h.",
  ];
  let py = 1.85;
  pts.forEach((p) => {
    s.addImage({ data: ic.check, x: 0.85, y: py + 0.02, w: 0.34, h: 0.34 });
    s.addText(p, { x: 1.35, y: py - 0.06, w: 10.8, h: 0.55, fontFace: BFONT, fontSize: 15.5, color: WHITE, valign: "middle", margin: 0, lineSpacingMultiple: 1.05 });
    py += 0.78;
  });

  s.addText("Run  gdexcp -h  for the full usage document.", { x: 0.85, y: 6.65, w: 11, h: 0.4, fontFace: BFONT, fontSize: 13, italic: true, color: ICE, margin: 0 });

  await pres.writeFile({ fileName: "/Users/zji/git/rda-python-miscs/docs/gdexcp_slides/gdexcp.pptx" });
  console.log("written");
})();
