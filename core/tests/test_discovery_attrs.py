"""Deterministic discovery language logic. Records below mirror what IKEA's own product pages state (fixtures, not live data)."""

from __future__ import annotations

import pytest

from ghostbuild_core.discovery import attrs as A
from ghostbuild_core.discovery.models import Attrs, ProductRecord


def rec(article, name, type_name, color, text, size="", ev=(), manual=()):
    return ProductRecord(
        source="ikea",
        article=article,
        name=name,
        type_name=type_name,
        color=color,
        size=size,
        description=text,
        evidence=list(ev),
        manual_evidence=list(manual),
        product_url=f"https://www.ikea.com/us/en/p/x-{article}/",
        verified_at=1,
    )


MICKE_1 = rec(
    "80213074",
    "MICKE",
    "desk",
    "white",
    "A clean and simple look. The clever design at the back hides messy cables.",
    '41 3/8x19 5/8"',
    ev=[
        "A white MICKE desk with silver accents. It has a sleek, minimalist design with one drawer and a cable management system."
    ],
    manual=["drawer", "cabinet with door", "2 shelves"],
)
MICKE_2 = rec(
    "90214308",
    "MICKE",
    "desk",
    "white",
    "A long table top makes it easy to create a workspace for two.",
    '55 7/8x19 5/8"',
    ev=[
        "A white MICKE desk. It a simple, minimalist design with two drawers, a cable management system, and clean lines."
    ],
)
MICKE_3 = rec(
    "30213076",
    "MICKE",
    "desk",
    "white",
    "Compact.",
    '28 3/4x19 5/8"',
    ev=[
        "White MICKE desk, minimalist, single drawer, cable management, rectangular shape."
    ],
)
ALEX = rec(
    "10473555",
    "ALEX",
    "desk",
    "white",
    "",
    '39 3/8x18 7/8"',
    ev=["White minimalist desk with metal legs and two drawers for compact storage."],
)
LAG = rec(
    "09521604",
    "LAGKAPTEN / ALEX",
    "desk",
    "white",
    "",
    '55 1/8x23 5/8"',
    ev=["This image an all-white ikea LAGKAPTEN desk with a cabinet and drawers."],
)
LINN = rec(
    "29932181",
    "LINNMON / ADILS",
    "table",
    "white",
    "",
    '39 3/8x23 5/8"',
    ev=["LINNMON white desk - modern, rectangular shape, four metallic legs."],
)
DRAWER_UNIT = rec(
    "00473546",
    "ALEX",
    "drawer unit",
    "white",
    "",
    "",
    ev=["White ALEX 5-drawer chest. Minimalist design."],
)
BLACK_DESK = rec(
    "10244743",
    "MICKE",
    "desk",
    "black-brown",
    "",
    "",
    ev=["Black MICKE desk with drawers & cable management."],
)
NAMES = ("MICKE", "ALEX", "LAGKAPTEN", "LINNMON")


def test_extract_the_demo_sentence():
    a = A.extract("I have a white IKEA desk with a drawer and cabinet.", NAMES)
    assert a.category == "desk" and a.color == "white"
    assert a.features == {
        "drawer": True,
        "cabinet": True,
    }  # 'a drawer' is presence, not exactly one
    assert a.name_hint is None


@pytest.mark.parametrize(
    "text,feat,val",
    [
        ("mine has two drawers", "drawer", 2),
        ("it has 3 drawers", "drawer", 3),
        ("no drawers at all", "drawer", False),
        ("with a single drawer", "drawer", 1),
        ("there is a cabinet on one side", "cabinet", True),
        ("rolling on wheels", "wheels", True),
    ],
)
def test_extract_counts_and_negations(text, feat, val):
    assert A.extract(text).features[feat] == val


def test_extract_name_and_colour_variants():
    a = A.extract("It's the black-brown MICKE", NAMES)
    assert a.name_hint == "MICKE" and a.color == "black-brown"
    assert (
        A.extract("a grey bookshelf").color == "grey"
        and A.extract("a gray bookshelf").color == "grey"
    )


def test_rank_orders_by_stated_evidence_and_never_invents():
    attrs = A.extract("white desk with a drawer and a cabinet", NAMES)
    out = A.rank([LINN, ALEX, MICKE_2, MICKE_1, LAG], attrs)
    names = [(c.record.article) for c in out]
    assert len(out) <= 5
    top = out[0]
    assert "drawer" in top.matched
    # a page that never says 'cabinet' is 'unverified', never 'matched'
    m1 = next(c for c in out if c.record.article == "80213074")
    assert "cabinet" in m1.matched  # supported by the cached manual evidence
    alex = next(c for c in out if c.record.article == "10473555")
    assert "cabinet" in alex.unverified and "cabinet" not in alex.matched
    assert names.index("09521604") < names.index(
        "10473555"
    )  # the page that states cabinet AND drawers outranks one that only states drawers


def test_rank_dedupes_by_article_but_keeps_different_products_with_the_same_name():
    out = A.rank(
        [MICKE_1, MICKE_1, MICKE_2, MICKE_3, BLACK_DESK, MICKE_1],
        A.extract("MICKE desk", NAMES),
    )
    arts = [c.record.article for c in out]
    assert (
        len(arts) == len(set(arts)) == 4
    )  # three white sizes + the black-brown one are four genuinely different products
    assert [c.rank for c in out] == [1, 2, 3, 4]


def test_rank_caps_at_five_and_drops_contradicted_category():
    many = [
        rec(
            f"1000000{i}", "MICKE", "desk", "white", "", ev=["white desk with a drawer"]
        )
        for i in range(8)
    ]
    assert len(A.rank(many + [DRAWER_UNIT], A.extract("white desk", NAMES))) == 5
    assert all(
        c.record.type_name == "desk"
        for c in A.rank(many + [DRAWER_UNIT], A.extract("white desk", NAMES))
    )


def test_count_conflict_is_a_conflict_not_a_match():
    out = A.rank([MICKE_1, MICKE_2], A.extract("white desk with two drawers", NAMES))
    assert out[0].record.article == "90214308" and "2 drawers" in out[0].matched
    other = next(c for c in out if c.record.article == "80213074")
    assert any("page says 1" in x for x in other.conflicts)


def test_no_match_returns_empty_not_a_guess():
    assert A.rank([LINN, DRAWER_UNIT], A.extract("a red sofa", NAMES)) == []


@pytest.mark.parametrize(
    "text,n,idx",
    [
        ("the first one", 5, 0),
        ("number three", 5, 2),
        ("Number 3", 5, 2),
        ("the second", 5, 1),
        ("#4", 5, 3),
        ("option 2", 5, 1),
        ("the last one", 5, 4),
        ("two", 3, 1),
        ("5", 5, 4),
        ("number nine", 5, None),
        ("blue", 5, None),
    ],
)
def test_pick_ordinal(text, n, idx):
    assert A.pick_ordinal(text, n) == idx


def test_pick_name():
    assert A.pick_name("That's MICKE", ["MICKE", "ALEX", "LAGKAPTEN / ALEX"]) == [0]
    assert A.pick_name("the alex one", ["MICKE", "ALEX", "LAGKAPTEN / ALEX"]) == [
        1
    ]  # whole-word on the NAME field only
    assert A.pick_name("it's the MICKE", ["MICKE", "MICKE", "ALEX"]) == [
        0,
        1,
    ]  # ambiguous: more than one product carries the name


@pytest.mark.parametrize(
    "text,none,more,number",
    [
        ("None of those", True, False, False),
        ("none of these", True, False, False),
        ("no, not any of them", True, False, False),
        ("show me more", False, True, False),
        ("any other options", False, True, False),
        ("more", False, True, False),
        ("I found the product number", False, False, True),
        ("I have the link", False, False, True),
        ("the first one", False, False, False),
    ],
)
def test_utterance_classes(text, none, more, number):
    assert (
        A.is_none(text) is none
        and A.is_more(text) is more
        and A.says_has_number(text) is number
    )


def test_distinguishing_question_comes_from_real_differences_only():
    cands = A.rank([MICKE_1, MICKE_2, MICKE_3], A.extract("white MICKE desk", NAMES))
    q = A.distinguishing_question(cands, A.extract("white MICKE desk", NAMES))
    assert (
        q is not None
        and q.feature == "drawer"
        and "how many drawers" in q.prompt.lower()
    )
    assert (
        q.options[-1] == "Not sure"
        and any("2 drawers" in o for o in q.options)
        and any("1 drawer" in o for o in q.options)
    )
    # the person already said the drawer count: do not ask again
    assert (
        A.distinguishing_question(cands, Attrs(features={"drawer": 2})) is None
        or A.distinguishing_question(cands, Attrs(features={"drawer": 2})).feature
        != "drawer"
    )


def test_no_question_when_candidates_do_not_differ():
    a, b = (
        rec("1", "X", "desk", "white", "", ev=["white desk"]),
        rec("2", "Y", "desk", "white", "", ev=["white desk"]),
    )
    assert (
        A.distinguishing_question(A.rank([a, b], Attrs(category="desk")), Attrs())
        is None
    )


def test_answer_to_attrs():
    cands = A.rank([MICKE_1, MICKE_2], A.extract("white MICKE desk", NAMES))
    q = A.distinguishing_question(cands, Attrs())
    assert A.answer_to_attrs(q, "two").features == {"drawer": 2}
    assert A.answer_to_attrs(q, "mine has 1 drawer").features == {"drawer": 1}
    assert A.answer_to_attrs(q, "not sure") is None


def test_drawer_unit_is_not_a_desk_even_if_its_caption_says_desk_drawers():
    unit = rec(
        "00473546",
        "ALEX",
        "drawer unit",
        "white",
        "",
        ev=["Open white desk drawer with office supplies, ALEX drawer unit"],
    )
    out = A.rank([unit, MICKE_1], A.extract("white desk with a drawer", NAMES))
    assert [c.record.article for c in out] == ["80213074"]


def test_a_table_filed_product_can_still_be_a_desk_match():
    out = A.rank([LINN], A.extract("white desk", NAMES))
    assert [c.record.article for c in out] == ["29932181"]


def test_accented_names_work_with_plain_text_and_material_is_kept():
    assert A.pick_name("It's the BLALIDEN", ["BLÅLIDEN", "BRIMNES"]) == [0]
    assert (
        A.extract("Help assemble my BLALIDEN cabinet", ("BLÅLIDEN",)).name_hint
        == "BLÅLIDEN"
    )
    attrs = A.extract("a small black metal cabinet")
    assert attrs.features["metal"] is True and "metal" in A.search_query(attrs)


def test_unknown_feature_is_not_a_zero_count_in_a_question():
    one = rec("1", "X", "desk", "white", "", ev=["one drawer"])
    unknown = rec("2", "Y", "desk", "white", "", ev=["a flat work surface"])
    assert (
        A.distinguishing_question(
            A.rank([one, unknown], Attrs(category="desk")), Attrs()
        )
        is None
    )
