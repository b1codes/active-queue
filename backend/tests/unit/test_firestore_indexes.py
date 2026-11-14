"""The composite-index checker used by the emulator tier, and the indexes file it reads.

`tests/emulator/conftest.py` runs every emulator-tier query through `IndexReport`, so a
query production Firestore would reject fails CI. These tests pin the checker's model of
Firestore's index rules and guard against a second, undeployed copy of the indexes file.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore import AsyncClient
from google.cloud.firestore_v1 import FieldFilter, Or

from tests.firestore_indexes import (
    ASC,
    DESC,
    INDEXES_PATH,
    REPO_ROOT,
    Index,
    IndexReport,
    QueryShape,
    UnsupportedQueryError,
    load_indexes,
    shape_of,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.async_query import AsyncQuery


@pytest.fixture(scope="module")
def client() -> AsyncClient:
    # Building a query needs no network or credentials.
    return AsyncClient(project="demo-index-check", credentials=AnonymousCredentials())


def _shape(query: AsyncQuery) -> QueryShape:
    return shape_of(query._to_protobuf())


def _index(collection: str, *fields: tuple[str, str], scope: str = "COLLECTION") -> Index:
    return Index(collection, scope, tuple(fields))


# --- The indexes file ---------------------------------------------------------------------


def test_one_indexes_file_and_both_firebase_configs_deploy_it() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "*firestore.indexes*.json"],  # noqa: S607 - git on PATH in CI
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert tracked == ["firestore.indexes.json"], (
        "Keep one Firestore indexes file. A second copy drifts, and only the one "
        f"firebase.json names is deployed. Found: {tracked}"
    )
    for config in ("firebase.json", "firebase.test.json"):
        raw = json.loads((REPO_ROOT / config).read_text())
        assert raw["firestore"]["indexes"] == "firestore.indexes.json", config


def test_indexes_file_is_well_formed() -> None:
    raw = json.loads(INDEXES_PATH.read_text())
    seen: set[str] = set()
    for entry in raw["indexes"]:
        assert entry["queryScope"] in ("COLLECTION", "COLLECTION_GROUP"), entry
        assert len(entry["fields"]) >= 2, f"single-field indexes are automatic: {entry}"
        for f in entry["fields"]:
            assert ("order" in f) != ("arrayConfig" in f), f
            assert f.get("order", ASC) in (ASC, DESC), f
            assert f.get("arrayConfig", "CONTAINS") == "CONTAINS", f
        key = json.dumps(entry, sort_keys=True)
        assert key not in seen, f"duplicate index: {entry}"
        seen.add(key)
    assert load_indexes(), "firestore.indexes.json declares no indexes"


# --- Query shapes ---------------------------------------------------------------------------


def test_shape_reads_filters_and_orders(client: AsyncClient) -> None:
    q = (
        client.collection("sessions")
        .where(filter=FieldFilter("user_id", "==", "u"))
        .where(filter=FieldFilter("status", "in", ["pending", "in_progress"]))
        .where(filter=FieldFilter("tags", "array_contains", "run"))
        .where(filter=FieldFilter("duration", ">", 5))
        .order_by("duration")
        .order_by("created_at", direction="DESCENDING")
    )
    shape = _shape(q)
    assert shape.collection == "sessions"
    assert shape.scope == "COLLECTION"
    assert shape.equality == {"user_id", "status"}
    assert shape.array_contains == {"tags"}
    assert shape.inequality == {"duration"}
    assert shape.effective_orders() == (("duration", ASC), ("created_at", DESC))


def test_collection_group_scope(client: AsyncClient) -> None:
    q = client.collection_group("items").where(filter=FieldFilter("a", "==", 1)).order_by("b")
    assert _shape(q).scope == "COLLECTION_GROUP"


def test_inequality_field_gets_an_implicit_ascending_sort(client: AsyncClient) -> None:
    q = client.collection("c").where(filter=FieldFilter("a", "==", 1))
    q = q.where(filter=FieldFilter("n", ">=", 3))
    assert _shape(q).effective_orders() == (("n", ASC),)


def test_name_sort_and_sorts_on_equality_fields_are_ignored(client: AsyncClient) -> None:
    q = (
        client.collection("c")
        .where(filter=FieldFilter("a", "==", 1))
        .order_by("a")
        .order_by("b", direction="DESCENDING")
        .order_by("__name__", direction="DESCENDING")
    )
    assert _shape(q).effective_orders() == (("b", DESC),)


def test_unary_filters(client: AsyncClient) -> None:
    q = client.collection("c").where(filter=FieldFilter("a", "==", None))
    q = q.where(filter=FieldFilter("b", "!=", None))
    shape = _shape(q)
    assert shape.equality == {"a"}
    assert shape.inequality == {"b"}


def test_or_filters_are_reported_not_guessed(client: AsyncClient) -> None:
    q = client.collection("c").where(
        filter=Or([FieldFilter("a", "==", 1), FieldFilter("b", "==", 2)])
    )
    with pytest.raises(UnsupportedQueryError, match="OR filter"):
        _shape(q)


@pytest.mark.parametrize(
    ("build", "needs"),
    [
        (lambda c: c.collection("c")._query(), False),
        (lambda c: c.collection("c").where(filter=FieldFilter("a", "==", 1)), False),
        (
            lambda c: (
                c.collection("c")
                .where(filter=FieldFilter("a", "==", 1))
                .where(filter=FieldFilter("b", "in", [1, 2]))
            ),
            False,
        ),
        (lambda c: c.collection("c").order_by("a"), False),
        (lambda c: c.collection("c").where(filter=FieldFilter("a", ">", 1)), False),
        (
            lambda c: c.collection("c").where(filter=FieldFilter("a", "==", 1)).order_by("b"),
            True,
        ),
        (
            lambda c: (
                c.collection("c")
                .where(filter=FieldFilter("a", "==", 1))
                .where(filter=FieldFilter("b", "<", 2))
            ),
            True,
        ),
        (lambda c: c.collection("c").order_by("a").order_by("b"), True),
    ],
    ids=[
        "no-filter",
        "one-equality",
        "equalities-merge",
        "single-field-sort",
        "single-field-range",
        "equality-plus-sort",
        "equality-plus-range",
        "two-sorts",
    ],
)
def test_needs_composite_index(client: AsyncClient, build: object, needs: bool) -> None:
    assert _shape(build(client)).needs_composite_index() is needs  # type: ignore[operator]


# --- Index matching -------------------------------------------------------------------------

_HISTORY = QueryShape(
    collection="sessions",
    equality=frozenset({"user_id", "status"}),
    orders=(("created_at", DESC),),
)


def test_index_with_equalities_in_any_order_serves() -> None:
    assert _index("sessions", ("status", ASC), ("user_id", ASC), ("created_at", DESC)).serves(
        _HISTORY
    )


def test_equality_field_direction_does_not_matter() -> None:
    assert _index("sessions", ("user_id", DESC), ("status", ASC), ("created_at", DESC)).serves(
        _HISTORY
    )


@pytest.mark.parametrize(
    "index",
    [
        _index("sessions", ("user_id", ASC), ("created_at", DESC)),  # missing equality field
        _index("sessions", ("user_id", ASC), ("status", ASC), ("created_at", ASC)),  # direction
        _index("sessions", ("user_id", ASC), ("created_at", DESC), ("status", ASC)),  # position
        _index("feed", ("user_id", ASC), ("status", ASC), ("created_at", DESC)),  # collection
        _index(
            "sessions",
            ("user_id", ASC),
            ("status", ASC),
            ("created_at", DESC),
            scope="COLLECTION_GROUP",
        ),
        _index(
            "sessions", ("user_id", ASC), ("status", ASC), ("created_at", DESC), ("x", ASC)
        ),  # extra field
    ],
    ids=[
        "missing-field",
        "wrong-direction",
        "sort-before-equality",
        "collection",
        "scope",
        "extra",
    ],
)
def test_mismatched_index_does_not_serve(index: Index) -> None:
    assert not index.serves(_HISTORY)


def test_reversed_index_is_not_assumed_to_serve() -> None:
    shape = QueryShape(collection="c", orders=(("b", ASC), ("d", DESC)))
    assert _index("c", ("b", ASC), ("d", DESC)).serves(shape)
    assert not _index("c", ("b", DESC), ("d", ASC)).serves(shape)
    assert not _index("c", ("b", DESC), ("d", DESC)).serves(shape)


def test_array_contains_needs_a_contains_field() -> None:
    shape = QueryShape(collection="c", array_contains=frozenset({"tags"}), orders=(("t", DESC),))
    assert _index("c", ("tags", "CONTAINS"), ("t", DESC)).serves(shape)
    assert not _index("c", ("tags", ASC), ("t", DESC)).serves(shape)


# --- The report -----------------------------------------------------------------------------


def test_report_flags_missing_index_with_a_ready_to_paste_suggestion(client: AsyncClient) -> None:
    report = IndexReport([])
    q = client.collection("sources").where(filter=FieldFilter("user_id", "==", "u"))
    q = q.order_by("updated_at", direction="DESCENDING")
    error = report.record(q._to_protobuf(), "test_x")
    assert error is not None
    assert "would reject" in error
    suggestion = json.loads(error.rsplit("firestore.indexes.json: ", 1)[1])
    assert Index.from_json(suggestion).serves(_shape(q))


def test_report_tracks_used_and_unused_indexes(client: AsyncClient) -> None:
    used = _index("sources", ("user_id", ASC), ("updated_at", DESC))
    unused = _index("activities", ("user_id", ASC), ("created_at", DESC))
    report = IndexReport([used, unused])
    q = client.collection("sources").where(filter=FieldFilter("user_id", "==", "u"))
    assert (
        report.record(q.order_by("updated_at", direction="DESCENDING")._to_protobuf(), "t") is None
    )
    assert report.unused() == [unused]


def test_report_records_unsupported_shapes(client: AsyncClient) -> None:
    report = IndexReport([])
    q = client.collection("c").where(
        filter=Or([FieldFilter("a", "==", 1), FieldFilter("b", "==", 2)])
    )
    assert report.record(q._to_protobuf(), "t") is not None
    assert report.unsupported
