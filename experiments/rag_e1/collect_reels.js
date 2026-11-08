// collect_reels.js — Step 1 of the E1 reel download (runs in YOUR browser)
// =========================================================================
// 1. In Chrome (logged in) open the creator's profile: instagram.com/<username>/
// 2. Ctrl+Shift+I -> Console tab. (First time only: Chrome asks you to type
//    "allow pasting" and press Enter before it accepts pasted code.)
// 3. Paste this whole file, press Enter, answer "how many reels".
//    Leave the tab open and in front: it scrolls the page by itself.
// 4. When it has enough, <username>_reels.json lands in your Downloads folder.
//    (Type saveReels() in the console to save early.)
// 5. Step 2:  python download_reels.py --json "$env:USERPROFILE\Downloads\<username>_reels.json" --creator "<folder>"
//
// How: Instagram's internal API endpoints change often, so this calls none of
// them. It listens to the data the page itself loads while scrolling (fetch +
// XHR responses, plus the JSON embedded in the page) and picks out every post
// object that has a shortcode and a video. Scrolling happens at a human pace
// (2.5-4.5 s). Video links expire after a few hours: run step 2 soon after.

(async () => {
  const PROFILE = ((location.pathname.match(/^\/([A-Za-z0-9._]+)\/?/) || [])[1] || "").toLowerCase();
  if (!PROFILE || ["explore", "reels", "direct", "p", "accounts"].includes(PROFILE)) {
    return console.error("[collect] Open the creator's profile page first (instagram.com/<username>/)");
  }
  const LIMIT = Number(prompt(`@${PROFILE}: how many reels? (50 recommended)`, "50"));
  if (!LIMIT) return console.log("[collect] cancelled");

  const reels = new Map(); // shortcode -> {shortcode, caption, video_url, taken_at}
  let noVideo = 0;

  // ── pick post objects out of any JSON, whatever its shape ──
  const captionOf = (n) =>
    (n.caption && n.caption.text) ||
    (n.edge_media_to_caption && n.edge_media_to_caption.edges && n.edge_media_to_caption.edges[0] &&
      n.edge_media_to_caption.edges[0].node.text) || "";
  const ownerOf = (n) => ((n.user && n.user.username) || (n.owner && n.owner.username) || "").toLowerCase();
  const videoOf = (n) => {
    if (Array.isArray(n.video_versions) && n.video_versions.length) {
      const area = (v) => (v.width || 0) * (v.height || 0);
      return n.video_versions.reduce((a, b) => (area(b) > area(a) ? b : a)).url;
    }
    return n.video_url || null;
  };
  const consider = (n) => {
    const code = n.code || n.shortcode;
    if (typeof code !== "string" || !(n.video_versions || n.video_url || n.media_type === 2 || n.is_video)) return;
    const owner = ownerOf(n);
    if (owner && owner !== PROFILE) return; // suggested posts from other accounts
    const url = videoOf(n);
    const prev = reels.get(code);
    if (prev && prev.video_url) return;
    if (!url) { if (!prev) noVideo++; reels.set(code, { shortcode: code, caption: captionOf(n), video_url: null, taken_at: n.taken_at }); return; }
    if (prev && !prev.video_url) noVideo--;
    reels.set(code, { shortcode: code, caption: captionOf(n) || (prev && prev.caption) || "", video_url: url, taken_at: n.taken_at || n.taken_at_timestamp });
  };
  const walk = (x, depth = 0) => {
    if (!x || typeof x !== "object" || depth > 40) return;
    if (Array.isArray(x)) { for (const v of x) walk(v, depth + 1); return; }
    consider(x);
    // Carousel slides are separate media objects with their own code and video,
    // but they are silent, caption-less clips, not reels: never descend into them.
    for (const k in x) if (k !== "carousel_media" && k !== "edge_sidecar_to_children") walk(x[k], depth + 1);
  };
  const ingest = (text) => {
    if (!text || text.length < 20) return;
    text = text.replace(/^for \(;;\);/, "");
    try { walk(JSON.parse(text)); return; } catch (_) {}
    for (const line of text.split(/\r?\n/)) { try { walk(JSON.parse(line)); } catch (_) {} } // streamed responses
  };
  const withVideo = () => [...reels.values()].filter((r) => r.video_url).length;

  // ── listen to what the page loads ──
  const origFetch = window.fetch;
  window.fetch = async function (...args) {
    const res = await origFetch.apply(this, args);
    try { res.clone().text().then(ingest).catch(() => {}); } catch (_) {}
    return res;
  };
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener("load", () => { try { if (!this.responseType || this.responseType === "text") ingest(this.responseText); } catch (_) {} });
    return origSend.apply(this, args);
  };
  document.querySelectorAll('script[type="application/json"]').forEach((s) => ingest(s.textContent)); // first posts are embedded in the page
  console.log(`[collect] @${PROFILE}: ${withVideo()} reels found in the page so far`);

  window.saveReels = () => {
    const list = [...reels.values()].filter((r) => r.video_url).slice(0, LIMIT);
    const out = { profile: PROFILE, collected_at: new Date().toISOString(), reels: list };
    const blob = new Blob([JSON.stringify(out, null, 1)], { type: "application/json" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${PROFILE}_reels.json` });
    document.body.appendChild(a); a.click(); a.remove();
    window.fetch = origFetch; XMLHttpRequest.prototype.send = origSend;
    console.log(`[collect] saved ${list.length} reels to Downloads/${PROFILE}_reels.json` +
                (noVideo ? ` (${noVideo} posts seen without a video link were skipped)` : ""));
  };

  // ── scroll at a human pace until enough, or nothing new for a while ──
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let last = -1, idle = 0;
  while (withVideo() < LIMIT && idle < 6) {
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(2500 + Math.random() * 2000);
    const n = withVideo();
    idle = n === last ? idle + 1 : 0;
    last = n;
    console.log(`[collect] ${n}/${LIMIT} reels with video` + (noVideo ? ` (+${noVideo} without link)` : ""));
  }
  if (idle >= 6) console.log("[collect] no new reels after 6 scrolls (end of profile, or Instagram stopped loading)");
  window.saveReels();
})().catch((e) => console.error("[collect] failed:", e));
