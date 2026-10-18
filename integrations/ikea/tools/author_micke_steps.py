"""Authoring record for knowledge/products/ikea/80213074/steps.json: the 35 steps of IKEA's MICKE (article 802.130.74) assembly manual
AA-476615-12, summarised from its diagrams by a person/assistant reading each page. Part numbers and quantities are copied exactly as the
manual prints them (build_manual.py cross-checks every number against the PDF's own text); a part the manual crosses out in a step is
recorded as avoid=true. Nothing in the step text goes beyond what the drawing shows. A human should still spot-check it against the PDF."""

import json
from pathlib import Path

P = {  # part id -> short descriptive name, from the drawings on manual pages 3-4 (the numbers are the manual's, the names are descriptive)
    "100086": "long bolt", "110519": "hammer-in bolt", "118331": "cam bolt", "110126": "cam lock", "103430": "cam lock", "103114": "cam lock",
    "100365": "small screw", "113287": "wide-head screw", "101514": "shelf pin", "101344": "wooden dowel", "104663": "adhesive bumper",
    "153549": "plastic fitting", "109221": "hinge plate", "121030": "tool strip", "100092": "hex key", "109338": "hinge", "112482": "drawer runner",
    "121304": "cable grommet", "112519": "round cover", "121338": "round cover", "10081375": "hexagon cover",
}


def part(i, qty=None, note=None, avoid=False, name=None):
    return {"id": i, "qty": qty, "name": name or P[i], "note": note, "avoid": avoid}


def nope(i, why="crossed out in this step"):
    return part(i, None, why, True)


S = []


def step(n, title, l1, l2, detail, parts=None, warn=None):
    S.append({"n": n, "title": title, "cue": [l1, l2], "detail": detail, "parts": parts or [], "warnings": warn or []})


NOQ = "quantity not printed in the manual"
step(1, "Screw in 2 cam bolts", "SCREW IN 2 CAM BOLTS", "PART 118331",
     "Screw two cam bolts 118331 into the holes in the ends of the long piece, using a screwdriver. The picture at the top of the page shows the drawer that steps 1 to 8 build.",
     [part("118331", 2)])
step(2, "Fit 2 dowels, join the sides", "FIT 2 DOWELS", "PART 101344",
     "Press two wooden dowels 101344 into the holes shown, then join the two upright side pieces to the long piece.", [part("101344", 2)])
step(3, "Fit 2 cam locks", "FIT 2 CAM LOCKS", "PART 103114 ONLY",
     "Press a cam lock 103114 into each side piece and turn it with a screwdriver as shown. The picture crosses out cam locks 110126 and 103430 for this step.",
     [part("103114", 2), nope("110126"), nope("103430")], ["Cam locks 110126 and 103430 are crossed out in this step: use only 103114."])
step(4, "Raise sides, slide in base", "SWING SIDES UP, SLIDE", "IN THE BASE PANEL",
     "Swing the side pieces up as the curved arrow shows, then slide the thin base panel in as the straight arrow shows. The close-up shows the panel's rough surface; match it to the manual's picture.")
step(5, "Fit the front panel", "FIT THE FRONT PANEL", "ONTO THE FRAME",
     "Swing the front panel up onto the frame as the arrow shows. The close-up shows the panel's edge seated in the groove.")
step(6, "Hammer in 2 bolts", "HAMMER IN 2 BOLTS", "PART 110519",
     "Tap two bolts 110519 into the holes shown with a hammer. The small picture at the corner shows where the hammer is used.", [part("110519", 2)])
step(7, "Place the drawer runners", "PLACE THE RUNNERS", "ON THE DRAWER SIDES",
     "Lower the two drawer runners onto the sides of the drawer as the arrows show. The runners are the parts on manual page 4 (112482, 2x). No fasteners in this step.")
step(8, "Screw on the runners", "SCREW ON THE RUNNERS", "4X 100365",
     "Fix each runner with screws 100365 (4x in total). The picture crosses out screw 113287.", [part("100365", 4), nope("113287")],
     ["Screw 113287 is crossed out in this step: use only 100365."])
step(9, "Fit 2 dowels", "FIT 2 DOWELS", "PART 101344",
     "Press two dowels 101344 into the narrow panel's edge as shown on the carpet. From this step the pages follow the side you chose for the cabinet.", [part("101344", 2)])
step(10, "Fit 2 dowels in the rail", "FIT 2 DOWELS IN RAIL", "HOLE SIDE AS SHOWN",
     "Press two dowels 101344 into the ends of the rail. The two small pictures show which way the holes must face; the crossed-out one is the orientation to avoid.",
     [part("101344", 2)], ["Check the two small pictures: the crossed-out hole orientation must not be used."])
step(11, "Screw in 8 cam bolts", "SCREW IN 8 CAM BOLTS", "PART 118331",
     "Screw eight cam bolts 118331 into the edges of the two panels as shown, using a screwdriver.", [part("118331", 8)])
step(12, "Screw runners onto panels", "SCREW RUNNERS ON", "USE SCREW 100365",
     "Fix one runner to each of the two panels with screws 100365. The picture crosses out screw 113287. The manual prints 1x for each runner and no screw count.",
     [part("100365", None, NOQ), nope("113287")], ["Screw 113287 is crossed out in this step: use only 100365."])
step(13, "Fit dowels, raise the sides", "FIT 2 DOWELS", "THEN RAISE THE SIDES",
     "Press two dowels 101344 into the rail ends, then raise the side panels as the arrows show.", [part("101344", 2)])
step(14, "Fit 8 cam locks", "FIT 8 CAM LOCKS", "PART 103430 ONLY",
     "Press eight cam locks 103430 into the holes shown and turn each a quarter turn with a screwdriver. The picture crosses out cam lock 110126.",
     [part("103430", 8), nope("110126")], ["Cam lock 110126 is crossed out in this step: use only 103430."])
step(15, "Screw runner onto panel", "SCREW RUNNER ON", "USE SCREW 100365",
     "Fix the runner to the panel with screws 100365, as in step 12. The picture crosses out screw 113287.",
     [part("100365", None, NOQ), nope("113287")], ["Screw 113287 is crossed out in this step: use only 100365."])
step(16, "Fit 2 hinge plates", "FIT 2 HINGE PLATES", "109221, SCREW 113287",
     "Fix two hinge plates 109221 with screws 113287; the plate's A mark is shown in the close-up. The picture crosses out screw 100365 for this step.",
     [part("109221", 2), part("113287", None, NOQ), nope("100365")], ["Screw 100365 is crossed out in this step: use 113287."])
step(17, "Screw in 4 cam bolts", "SCREW IN 4 CAM BOLTS", "PART 118331",
     "Screw four cam bolts 118331 into the panel edges shown, using a screwdriver.", [part("118331", 4)])
step(18, "Slide in the back panel", "SLIDE IN BACK PANEL", "SEE ROUGH-SIDE NOTE",
     "Slide the thin back panel in as the arrow shows. The picture crosses out the rough, textured side: check which side the manual shows.", [],
     ["The rough, textured side is crossed out in the picture."])
step(19, "Fit 2 cam locks", "FIT 2 CAM LOCKS", "PART 110126",
     "Press two cam locks 110126 into the holes shown and turn each with a screwdriver.", [part("110126", 2)])
step(20, "Fit 4 dowels", "FIT 4 DOWELS", "PART 101344",
     "Press four dowels 101344 into the edges of the small panel as shown. The close-up shows the panel's edge.", [part("101344", 4)])
step(21, "Raise the side panel", "RAISE THE SIDE PANEL", "ONTO THE DOWELS",
     "Swing the side panel up as the arrow shows so its dowels enter their holes.")
step(22, "Fit 2 cam locks", "FIT 2 CAM LOCKS", "PART 110126",
     "Press two cam locks 110126 into the holes shown and turn each with a screwdriver.", [part("110126", 2)])
step(23, "Fit 6 dowels", "FIT 6 DOWELS", "PART 101344",
     "Press six dowels 101344 into the holes shown along the panel edges.", [part("101344", 6)])
step(24, "Bolt on the leg frame", "BOLT ON THE LEG FRAME", "3X 100086, HEX KEY",
     "Attach the metal leg frame with three long bolts 100086, turned with hex key 100092. The small picture at the top shows how the hex key 100092 fits into strip 121030.",
     [part("100086", 3), part("100092", 1), part("121030", 1)])
step(25, "Screw in 6 cam bolts", "SCREW IN 6 CAM BOLTS", "PART 118331",
     "Screw six cam bolts 118331 into the large panel lying on the carpet, using a screwdriver.", [part("118331", 6)])
step(26, "Join the frame and the panel", "JOIN FRAME AND PANEL", "AS THE ARROW SHOWS",
     "Move the assembled frame and the large panel together as the arrow shows, lining the cam bolts up with their holes.")
step(27, "Fit 6 cam locks", "FIT 6 CAM LOCKS", "PART 110126",
     "Press six cam locks 110126 into the holes shown and turn each with a screwdriver.", [part("110126", 6)])
step(28, "Fit 4 plastic fittings", "FIT 4 PLASTIC FITTINGS", "PART 153549",
     "Push four plastic fittings 153549 into the holes shown, as the close-up pictures.", [part("153549", 4)])
step(29, "Press in 2 hexagon covers", "PRESS IN 2 HEX COVERS", "PART 10081375",
     "Press the hexagon covers 10081375 into the holes of the leg frame, by hand. The picture crosses out the round covers 112519 and 121338 for this step.",
     [part("10081375", 2), nope("112519"), nope("121338")], ["The round covers 112519 and 121338 are crossed out in this step."])
step(30, "Hang the drawer", "HANG THE DRAWER", "ON ITS RUNNERS",
     "Tilt the drawer up and let its runners catch the rails as the arrow and the top close-up show, then slide it in.")
step(31, "Fit 2 hinges on the door", "FIT 2 HINGES ON DOOR", "109338, SCREW 100365",
     "Lay the door flat and fix two hinges 109338 with screws 100365, as the close-up shows.",
     [part("109338", 2), part("100365", None, NOQ)])
step(32, "Hang the door", "HANG THE DOOR", "CLIP ON, TIGHTEN SCREW",
     "Clip each hinge onto its plate as the arrow shows, then tighten the hinge screw with a screwdriver. Manual page 40 shows how to adjust the door; it is the third picture for this step.",
     [part("109338", 2, "already fixed to the door in step 31")])
step(33, "Fit 8 shelf pins and shelves", "FIT 8 SHELF PINS", "PART 101514",
     "Push eight shelf pins 101514 into the holes and rest the two shelves on them, as the arrows show.", [part("101514", 8)])
step(34, "Stick on 2 bumpers", "STICK ON 2 BUMPERS", "PART 104663",
     "Stick two adhesive bumpers 104663 where the close-up shows.", [part("104663", 2)])
step(35, "Fit the grommet and covers", "FIT GROMMET + 4 COVERS", "121304 AND 112519",
     "Press the cable grommet into the hole in the top and the four round covers over the holes shown. The manual prints alternate numbers for these parts: grommet 121208, 121186 or 10060533; covers 121338 or 130521.",
     [part("121304", 1, "alternate numbers printed: 121208, 121186, 10060533"), part("112519", 4, "alternate numbers printed: 121338, 130521")])

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[3] / "knowledge" / "products" / "ikea" / "80213074" / "steps.json"
    out.write_text(json.dumps({"article": "80213074", "manual": "AA-476615-12", "steps": S}, indent=1))
    print(len(S), "steps ->", out)
