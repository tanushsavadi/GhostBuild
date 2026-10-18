#!/usr/bin/env python3
"""Original fold-geometry drawings. No downloaded tutorial pixels or traced artwork.

Reference: https://origami.me/cup/ steps 1-4 (inspected 2026-10-17).
Coordinates derive from an isosceles right triangle: left=(-1,0), top=(0,1), right=(1,0).
Bisecting the left 45-degree angle places the reference pinch at (sqrt(2)-1, 2-sqrt(2)).
Reflecting the left corner to that point gives the first side fold. The other side is symmetric.
Generate sources/specifications, then run assets/build_guides.py for crop/annotation/tone/gray4 outputs.
These are diagrams of intended folds, never observations or verification of the wearer's paper.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "sources"
W, H = 1200, 600
SCALE = 430
PAPER, FLAP, EDGE = (38, 48, 44), (74, 91, 80), (178, 200, 184)
T, L, R = (0., 1.), (-1., 0.), (1., 0.)
U = math.sqrt(2) - 1
PINCH, OPPOSITE = (U, 1-U), (-U, 1-U)
BASE_LEFT, BASE_RIGHT = (-U*U, 0.), (U*U, 0.)
SOURCE = "https://origami.me/cup/"


def xy(p):
    return (round(600 + SCALE*p[0]), round(470 - SCALE*p[1]))


def poly(d, points, fill=PAPER):
    points = [xy(p) for p in points]
    d.polygon(points, fill=fill)
    d.line(points + points[:1], fill=EDGE, width=7, joint="curve")


def line(d, a, b, dashed=False):
    a, b = xy(a), xy(b)
    if not dashed:
        d.line([a,b], fill=EDGE, width=6)
        return
    dist = math.dist(a,b)
    for n in range(int(dist/31)+1):
        lo, hi = n*31/dist, min((n*31+17)/dist, 1)
        if lo <= 1:
            d.line([(a[0]+(b[0]-a[0])*lo,a[1]+(b[1]-a[1])*lo),
                    (a[0]+(b[0]-a[0])*hi,a[1]+(b[1]-a[1])*hi)], fill=(124,147,133),width=6)


def source_shape(stage):
    img = Image.new("RGB", (W,H), (0,0,0))
    d = ImageDraw.Draw(img)
    if stage.startswith("diamond"):
        # A square diamond, separate scale to keep its full height readable.
        pts=[(600,55),(810,265),(600,475),(390,265)]
        d.polygon(pts, fill=PAPER)
        d.line(pts+pts[:1],fill=EDGE,width=7,joint="curve")
        if stage == "diamond_crease":
            for x in range(390,810,30):
                d.line([(x,265),(min(x+16,810),265)],fill=EDGE,width=6)
        return img
    if stage in ("left_done", "right_before", "right_done"):
        poly(d, [T,R,BASE_LEFT,OPPOSITE])
        poly(d, [OPPOSITE,BASE_LEFT,PINCH], FLAP)
        if stage == "right_done":
            # Right flap folds over the first; the outline is the pentagon T,P,D,B,Q.
            img = Image.new("RGB",(W,H),(0,0,0));d=ImageDraw.Draw(img)
            poly(d,[T,PINCH,BASE_RIGHT,BASE_LEFT,OPPOSITE])
            poly(d,[OPPOSITE,BASE_LEFT,PINCH],FLAP)
            poly(d,[PINCH,BASE_RIGHT,OPPOSITE],(95,117,102))
        return img
    poly(d,[T,R,L])
    if stage == "pinch_fold":
        # A guide line, not a full crease: only mark the short segment at the right edge.
        line(d,L,PINCH,dashed=True)
    if stage in ("pinch_done", "left_before", "left_fold"):
        x,y=xy(PINCH)
        d.line([(x-12,y-12),(x+12,y+12)],fill=(228,240,231),width=8)
    if stage == "left_fold":
        line(d,OPPOSITE,BASE_LEFT,dashed=True)
    return img


def ann_circle(p,r=38):
    x,y=xy(p);return {"type":"circle","cx":x,"cy":y,"r":r}


def ann_arrow(a,b):
    return {"type":"arrow","from":list(xy(a)),"to":list(xy(b))}


def entry(name, stage, caption, annotation, fallback, depicts):
    return {"view":name,"step_id":"", "title":name.upper(),"source":f"{name}.src.png",
            "crop":[0,0,W,H],"annotation":annotation,"caption":caption,"autocontrast":0,
            "contrast":1.05,"gamma":1,"provenance":"AUTHORED DEMO METADATA",
            "fallback_cue":{"line1":fallback[0],"line2":fallback[1]},
            "depicts":"Original instructional diagram: "+depicts+". Not a photo or a live observation.","_stage":stage}


def generate():
    specs={
      "cup_fold_half": ("FOLD IN HALF",[
        entry("where","diamond","BOTTOM TIP",{"type":"circle","cx":600,"cy":465,"r":40},("BOTTOM TIP OF DIAMOND","WHITE SIDE UP"),"square paper in diamond orientation, bottom tip highlighted"),
        entry("how","diamond_crease","BRING TIPS TOGETHER",{"type":"arrow","from":[600,450],"to":[600,78]},("BRING BOTTOM TIP UP","TO THE TOP TIP"),"bottom tip moves to top tip; dashed horizontal line marks the fold"),
        entry("correct","triangle","TRIANGLE; BASE CLOSED",{"type":"rect","x0":170,"y0":450,"x1":1030,"y1":487},("TRIANGLE WITH TWO LAYERS","CLOSED FOLD AT BOTTOM"),"two-layer triangular result with the closed bottom edge highlighted")]),
      "cup_pinch": ("MARK THE REFERENCE",[
        entry("where","triangle","TOP LAYER: LEFT EDGE",ann_arrow((-.72,.9),(-.55,.45)),("TOP LAYER LEFT EDGE","LEAVE LOWER LAYER FLAT"),"left sloping edge of the top triangle layer identified"),
        entry("how","pinch_fold","ALIGN; PINCH ONLY",ann_arrow((-.15,.82),(.30,.06)),("LOWER LEFT EDGE TO BASE","PINCH RIGHT EDGE ONLY"),"temporary angle-bisector fold bringing the left edge onto the bottom edge; pinch is where the guide meets the right edge"),
        entry("correct","pinch_done","UNFOLD; KEEP ONE MARK",ann_circle(PINCH), ("UNFOLD BACK TO TRIANGLE","SMALL MARK ON RIGHT EDGE"),"triangle reopened after the temporary fold; the precise small reference pinch is highlighted on the right edge")]),
      "cup_left_corner": ("LEFT TIP TO THE MARK",[
        entry("where","left_before","LEFT TIP + RIGHT MARK",ann_circle(L,42),("FIND THE LEFT TIP","RIGHT EDGE HAS THE MARK"),"left base tip highlighted, small reference mark visible on the opposite sloping edge"),
        entry("how","left_fold","LEFT TIP TO THE MARK",ann_arrow((-.95,.03),(U-.03,1-U-.02)),("BRING LEFT TIP TO MARK","CREASE THE NEW FOLD"),"left tip moves to the right-edge reference mark; dashed line gives the resulting crease"),
        entry("correct","left_done","FLAP TOP IS LEVEL",{"type":"rect","x0":410,"y0":200,"x1":790,"y1":236},("TIP MEETS RIGHT MARK","FLAP TOP EDGE LEVEL"),"first side flap folded across the triangle with a horizontal upper edge")]),
      "cup_right_corner": ("FOLD THE OTHER SIDE",[
        entry("where","right_before","RIGHT TIP IS STILL FREE",ann_circle(R,42),("FIND FREE RIGHT TIP","KEEP FIRST FLAP FLAT"),"unfolded right base tip highlighted after the left side fold"),
        entry("how","right_before","RIGHT TIP TO LEFT EDGE",ann_arrow((.95,.03),(-U+.03,1-U-.02)),("FOLD RIGHT TIP ACROSS","MATCH FIRST FLAP HEIGHT"),"right tip crosses to the left end of the horizontal first-flap edge"),
        entry("correct","right_done","MATCH THE TOP EDGES",{"type":"rect","x0":410,"y0":200,"x1":790,"y1":236},("BOTH SIDE FLAPS FOLDED","TOP EDGES AT SAME HEIGHT"),"both side flaps overlap with aligned horizontal upper edges and the upper triangle still free")])
    }
    for gid,(title,views) in specs.items():
        folder=ROOT/gid;folder.mkdir(parents=True,exist_ok=True)
        for view in views:
            source_shape(view.pop("_stage")).save(folder/view["source"])
            view["step_id"]=f"{gid}.{view['view']}"
        spec={"guide_id":gid,"title":title,"placeholder":False,"asset_kind":"original_diagram",
              "reference_url":SOURCE,"units":"px","views":views}
        (folder/"annotations.json").write_text(json.dumps(spec,indent=2)+"\n")
    print(f"Generated {len(specs)*3} original diagram sources; no tutorial images copied")


if __name__ == "__main__":
    generate()
