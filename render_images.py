#!/usr/bin/env python3
"""BetSweep card images — v2026-10-14.
Pre-renders every card on a built page to PNG with headless Chromium, then rewrites the page so the
"Copy card as image" / "Story 9:16" buttons become plain links to those PNGs (works in every browser;
the in-page html2canvas path fails on Safari/Firefox inside the artifact sandbox with "operation is insecure").

usage: python3 render_images.py out/matchup-boards.html [img_dir=out/img] [url_prefix=img]
Writes <img_dir>/<cardid>.png (full card, 2x) and <img_dir>/<cardid>-story.png (1080x1920).
Exit code 0 even when a card fails; a card that fails keeps its JS buttons.
"""
import asyncio, os, re, sys, json
from playwright.async_api import async_playwright

page_path = os.path.abspath(sys.argv[1]); img_dir = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(page_path), "img"))
prefix = sys.argv[3] if len(sys.argv) > 3 else "img"
os.makedirs(img_dir, exist_ok=True)

PREP = """
() => {
  // page-level: hide sticky chrome and the in-page screenshot leftovers so element shots are clean
  document.body.classList.remove('compact'); document.body.classList.add('render'); document.querySelectorAll('.card').forEach(c => c.classList.add('expanded'));
  const st = document.createElement('style'); st.id='__shot';
  st.textContent = `.top{position:static !important} .shotwrap{display:none !important} .ft .snap{display:none !important}
    .card.shooting{box-shadow:none}`;
  document.head.appendChild(st);
  return [...document.querySelectorAll('section.card[id]')].map(e => e.id);
}
"""
STORY = """
(id) => {
  const card = document.getElementById(id);
  const frame = document.createElement('div'); frame.className = 'storyframe'; frame.id = '__story';
  frame.style.cssText = 'position:fixed;left:0;top:0;z-index:9999;width:540px;height:960px;overflow:hidden;pointer-events:auto;';
  const inner = document.createElement('div'); inner.style.cssText = 'width:540px;transform-origin:top left;';
  const head = document.createElement('div'); head.className = 'shead';
  const logo = document.querySelector('.mast img'); if (logo) { const im = document.createElement('img'); im.src = logo.src; head.appendChild(im); }
  const bb = document.createElement('b'); bb.textContent = 'BetSweep'; head.appendChild(bb);
  const wk = document.createElement('span'); wk.textContent = (document.querySelector('.mast h1') || {}).textContent || ''; head.appendChild(wk);
  const clone = card.cloneNode(true); clone.removeAttribute('id'); clone.classList.remove('open');
  clone.querySelectorAll('.shotwrap,.snap').forEach(b => b.remove());
  const foot = document.createElement('p'); foot.className = 'sfoot'; foot.textContent = 'Picks. Data. Edge. Sweep.';
  inner.appendChild(head); inner.appendChild(clone); inner.appendChild(foot); frame.appendChild(inner); document.body.appendChild(frame);
  // frame padding is 18/14/22 -> inner box is 512 wide, 920 tall. Fit to height by scaling, widening the
  // layout by the same factor so the scaled result still fills the width (iterate: wider -> shorter).
  let k = 1, h = inner.scrollHeight;
  for (let i = 0; i < 4 && h * k > 920; i++) { k = 920 / h; inner.style.width = (512 / k) + 'px'; h = inner.scrollHeight; }
  k = Math.min(1, 920 / h); inner.style.width = (512 / k) + 'px'; h = inner.scrollHeight;
  if (h * k > 920) { k = 920 / h; inner.style.width = (512 / k) + 'px'; h = inner.scrollHeight; }
  inner.style.transform = `scale(${k})`;
  if (h * k < 920) inner.style.marginTop = ((920 - h * k) / 2) + 'px';
  return {h, k: +k.toFixed(3)};
}
"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1180, "height": 900}, device_scale_factor=2, color_scheme="dark")
        pg = await ctx.new_page()
        await pg.goto("file://" + page_path); await pg.wait_for_timeout(1200)
        ids = await pg.evaluate(PREP)
        done = {}
        if not ids:   # a page without cards (the parlay builder): one preview shot of the main panel for the landing tile
            await pg.evaluate("document.querySelectorAll('[id^=tk-],.tick,.livetag,.stx').forEach(function(e){ e.style.display='none'; })")   # no offline live-score messages in the landing tile
            el = await pg.query_selector("section.panel") or await pg.query_selector("main") or await pg.query_selector("body")
            out_p = os.path.join(img_dir, "preview.png"); await el.screenshot(path=out_p)
            try:   # crop to 16:9 for the landing tile
                from PIL import Image; im = Image.open(out_p); im.crop((0, 0, im.width, min(im.height, int(im.width * 9 / 16)))).save(out_p)
            except Exception: pass
            print(f"rendered preview -> {out_p}"); return
        for cid in ids:
            try:
                card = await pg.query_selector(f"#{cid}")
                await pg.evaluate("(id)=>{document.getElementById(id).classList.add('open')}", cid)
                await card.scroll_into_view_if_needed(); await pg.wait_for_timeout(50)
                await card.screenshot(path=os.path.join(img_dir, f"{cid}.png"))
                await pg.evaluate("(id)=>{document.getElementById(id).classList.remove('open')}", cid)
                info = await pg.evaluate(STORY, cid); await pg.wait_for_timeout(50)
                fr = await pg.query_selector("#__story"); await fr.screenshot(path=os.path.join(img_dir, f"{cid}-story.png"))
                await pg.evaluate("()=>{document.getElementById('__story').remove()}")
                done[cid] = info
            except Exception as e:
                print(f"  {cid}: FAILED {e}");
                try: await pg.evaluate("()=>{const f=document.getElementById('__story'); if(f) f.remove();}")
                except Exception: pass
        await b.close()
    html = open(page_path).read(); n = 0
    for cid in done:
        a = f'<button class="snap" type="button" data-target="{cid}">Copy card as image</button>'
        s = f'<button class="snap story" type="button" data-target="{cid}">Story 9:16</button>'
        a2 = f'<a class="snap" href="{prefix}/{cid}.png" target="_blank" rel="noopener">Card image</a>'
        s2 = f'<a class="snap story" href="{prefix}/{cid}-story.png" target="_blank" rel="noopener">Story 9:16</a>'
        if a in html and s in html: html = html.replace(a, a2).replace(s, s2); n += 1
    open(page_path, "w").write(html)
    tot = sum(os.path.getsize(os.path.join(img_dir, f)) for f in os.listdir(img_dir)) / 1e6
    print(f"rendered {len(done)}/{len(ids)} cards -> {img_dir} ({tot:.1f} MB); relinked {n} footers in {os.path.basename(page_path)}")
    print(json.dumps({k: v for k, v in done.items()}))

asyncio.run(main())
