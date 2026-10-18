# Guide images (lane A) - how to drop in REAL rig photos

The three images in `knowledge/guides/camera_lens/` are **SCHEMATIC STAND-INS** drawn from code
(`assets/tools/make_standin_sources.py`). They are **not photos of our rig**, show no connectors or pins, and every one is
marked `placeholder: true`, provenance `AUTHORED DEMO METADATA`, with a red `SCHEMATIC - REPLACE WITH RIG PHOTO` banner on the
phone image. Replace them before the demo. Total time with the helper: about 2 minutes per photo.

## Playbook stand-ins (paper_cup)
`cup_fold_half` (where/how/correct) and `cup_pinch` (where/how) are generic flat schematics of a square sheet and the triangle it
becomes (`assets/tools/make_standin_paper_cup.py`). They follow only the sentences of the cited tutorial (https://origami.me/cup/,
steps 1 and 2), carry `placeholder: true`, provenance `AUTHORED DEMO METADATA`, and a phone banner `SCHEMATIC - REPLACE WITH PHOTO`
(set by the guide-level `"banner"` key in `annotations.json`; without it the banner says `... RIG PHOTO`). The position of the
step-2 pinch is deliberately NOT drawn. Replace them with photos of a real folded sheet, same file names, `"placeholder": false`.
Every playbook picture step needs a guide in the card AND a folder here; at most two steps per card get one.

## What the G2 gets
`knowledge/guides/<guide_id>/<view>.png`: 8-bit greyscale PNG, exactly **288x144**, pixel values only 0,17,...,255 (= the 16 gray4
levels), black = transparent on the glasses. The size is fixed because the plugin's image container must match it
(`imageSizeInvalid` otherwise); a photo that is not 2:1 is letterboxed on black. `<view>.phone.png` is the high-res colour
version for the phone page. `manifest.json` has sizes, sha256 and a paste-ready `guide` object for the card's `guides[]`.

## Steps (per guide `camera_lens`, views `where`, `how`, `correct`)
1. **Take 3 photos** with the phone, landscape. Good G2 photos: subject large and centred, **dark/plain background**
   (bright background = a glowing green slab on the glasses), side light, no clutter. WHERE = the station with the camera lens
   visible. HOW = the cover/flap being removed (or the lens close up). CORRECT = lens uncovered / clear view.
2. Put them in `assets/sources/camera_lens/` as `where.jpg`, `how.jpg`, `correct.jpg` (any of png/jpg; the name must match `source` below).
   Do not rename later without updating `annotations.json`.
3. **Open `assets/tools/annotate_helper.html`** in a browser (double-click; works offline). For each photo: choose the file,
   drag the yellow crop box (locked to 2:1) tight around the subject, switch to "2 Highlight", drag the ONE highlight
   (circle = centre outwards, arrow = tail to tip, rect = corner to corner), set view/title/caption/fallback text, press
   "Add / replace this view". Do all three, press "Copy JSON".
   Set `provenance` in the dropdown (use `AUTHORED DEMO METADATA` for our own rig photos).
4. Paste into `assets/sources/camera_lens/annotations.json` (replace the whole file). In the pasted JSON make sure
   `"placeholder": false` (the helper writes false). A view-level `"placeholder": true` keeps one view flagged.
5. `make guides` (or `uv run python assets/build_guides.py camera_lens`). Look at `knowledge/guides/camera_lens/*.png`; if too
   bright/flat add `"gamma": 0.6` (below 1 darkens), `"contrast": 1.3` or `"autocontrast": 2` to that view and rebuild.
6. `uv run pytest -q assets/tests`, then commit `assets/sources/`, `knowledge/guides/`, `assets/INVENTORY.md`.
   Tell the knowledge owner nothing else: the card already points at `knowledge/guides/camera_lens/<view>.png`.

## annotations.json template
```json
{
  "guide_id": "camera_lens",
  "title": "Camera lens",
  "placeholder": false,
  "units": "px",
  "views": [
    {
      "view": "where",
      "step_id": "camera_lens.where",
      "title": "WHERE",
      "source": "where.jpg",
      "crop": [x0, y0, x1, y1],
      "annotation": {"type": "circle", "cx": 0, "cy": 0, "r": 0},
      "caption": "CAMERA LENS",
      "provenance": "AUTHORED DEMO METADATA",
      "depicts": "what the picture really shows, one sentence",
      "fallback_cue": {"line1": "CHECK CAMERA LENS", "line2": ""},
      "fov_note": "optional: which part of the Pi's field of view",
      "gamma": 1.0, "contrast": 1.0, "autocontrast": 1.0
    }
  ]
}
```
* `view`: `where` | `how` | `correct`. `title` <= 24 chars (it is `GuideView.title`). `caption` <= 24 chars (burned into the G2 image, optional).
  `fallback_cue` = the G2 text if the image fails (`line1` <= 24, `line2` <= 26). `step_id` must match the card's step ids.
* `provenance` must be one of the `EvidenceLabel` values (the build refuses anything else). Never label a stand-in as MEASURED LIVE.
* `annotation`: **exactly one object** (never a list): circle `{type,cx,cy,r}`, rect `{type,x0,y0,x1,y1}`, arrow `{type,from:[x,y],to:[x,y]}`
  (the tip is `to`). Drawn last, in max brightness with a black halo, aliased on purpose so it survives 4-bit quantization.
* **Coordinates** are in pixels of the ORIGINAL photo (`"units": "px"`; or `"units": "frac"` with 0..1 fractions of width/height,
  `r` as a fraction of width). Measure them with the helper, or in Preview/GIMP (cursor position = pixel), or in code
  `PIL.Image.open(f).size`. The highlight target must lie inside `crop` (the build says so otherwise).
* `crop`: `[x0,y0,x1,y1]`, ideally 2:1 so nothing is letterboxed. Aggressive crops read best at 288x144: the subject should fill the frame.
* Optional: `caption_pos` (`bottom`|`top`; put it opposite the highlight), `g2_size` `[w,h]` (<= [288,144], only if B uses a smaller container).

## Commands
| what | command |
|---|---|
| build all guides | `make guides` |
| one guide | `uv run python assets/build_guides.py camera_lens` |
| verify committed outputs are fresh (no write) | `uv run python assets/build_guides.py --check` |
| tests | `uv run pytest -q assets/tests` |
| regenerate the schematic stand-ins | `uv run python assets/tools/make_standin_sources.py` |

Builds are byte-deterministic (no timestamps), so a rebuild with unchanged inputs produces no git diff.
`assets/INVENTORY.md` is rewritten on every build. A broken `annotations.json` or missing photo fails with a plain message naming the file and field,
and writes nothing for that guide.
