"""Check Firestore queries against the composite indexes in `firestore.indexes.json`.

The Firestore emulator serves every query whether or not an index exists, but production
Firestore rejects a query with FAILED_PRECONDITION ("The query requires an index") when no
declared index can serve it. Without a check, a missing index surfaces only after deploy,
as a 500 on whichever endpoint runs the query.

The emulator tier (`tests/emulator/conftest.py`) records the StructuredQuery of every query
the app sends and checks each one here, so the tier fails the way production would.

The model is deliberately conservative. It accepts a query when:

- it needs no composite index: equality-only filters (merged from single-field indexes),
  or only one field in total, or
- a declared index matches it exactly: the equality fields first, in any order, then the
  sort fields in query order with the same directions.

Firestore can sometimes serve a query in other ways, such as zig-zag merging two composite
indexes. This check doesn't model those cases, and it doesn't assume an index can be read
in reverse. Declare the exact index instead, which is also what the Firestore console's
"create index" link for a failed query gives you.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.cloud.firestore_v1.types import StructuredQuery

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEXES_PATH = REPO_ROOT / "firestore.indexes.json"

_FieldOp = StructuredQuery.FieldFilter.Operator
_UnaryOp = StructuredQuery.UnaryFilter.Operator
_Direction = StructuredQuery.Direction

_EQUALITY_OPS = {_FieldOp.EQUAL, _FieldOp.IN}
_ARRAY_OPS = {_FieldOp.ARRAY_CONTAINS, _FieldOp.ARRAY_CONTAINS_ANY}
_INEQUALITY_OPS = {
    _FieldOp.LESS_THAN,
    _FieldOp.LESS_THAN_OR_EQUAL,
    _FieldOp.GREATER_THAN,
    _FieldOp.GREATER_THAN_OR_EQUAL,
    _FieldOp.NOT_EQUAL,
    _FieldOp.NOT_IN,
}
_UNARY_EQUALITY_OPS = {_UnaryOp.IS_NULL, _UnaryOp.IS_NAN}

ASC = "ASCENDING"
DESC = "DESCENDING"


class UnsupportedQueryError(ValueError):
    """The query uses a shape this checker doesn't model (for example an OR filter)."""


@dataclass(frozen=True)
class QueryShape:
    """The parts of a query that decide which index serves it."""

    collection: str
    collection_group: bool = False
    equality: frozenset[str] = frozenset()
    array_contains: frozenset[str] = frozenset()
    inequality: frozenset[str] = frozenset()
    orders: tuple[tuple[str, str], ...] = ()

    @property
    def scope(self) -> str:
        return "COLLECTION_GROUP" if self.collection_group else "COLLECTION"

    def effective_orders(self) -> tuple[tuple[str, str], ...]:
        """Explicit sorts plus the ascending sorts Firestore adds for inequality fields.

        `__name__` is dropped: Firestore appends it to every index implicitly.
        """
        # A sort on a field already fixed by an equality filter is a no-op for indexing.
        orders = [(f, d) for f, d in self.orders if f != "__name__" and f not in self.equality]
        ordered = {f for f, _ in orders}
        orders.extend((f, ASC) for f in sorted(self.inequality - ordered))
        return tuple(orders)

    def needs_composite_index(self) -> bool:
        orders = self.effective_orders()
        if not orders:
            # Equality and array-contains filters only: single-field index merging.
            return False
        fields = self.equality | self.array_contains | {f for f, _ in orders}
        return len(fields) > 1

    def describe(self) -> str:
        parts = [f"{f} ==" for f in sorted(self.equality)]
        parts += [f"{f} array-contains" for f in sorted(self.array_contains)]
        parts += [f"{f} {d}" for f, d in self.effective_orders()]
        return f"{self.collection} ({self.scope}): " + ", ".join(parts)

    def suggested_index(self) -> dict[str, Any]:
        fields: list[dict[str, str]] = [
            {"fieldPath": f, "order": ASC} for f in sorted(self.equality)
        ]
        fields += [
            {"fieldPath": f, "arrayConfig": "CONTAINS"} for f in sorted(self.array_contains)
        ]
        fields += [{"fieldPath": f, "order": d} for f, d in self.effective_orders()]
        return {"collectionGroup": self.collection, "queryScope": self.scope, "fields": fields}


@dataclass(frozen=True)
class Index:
    collection: str
    scope: str
    fields: tuple[tuple[str, str], ...]  # (fieldPath, ASCENDING | DESCENDING | CONTAINS)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Index:
        fields = tuple(
            (f["fieldPath"], f.get("order") or f.get("arrayConfig", "")) for f in raw["fields"]
        )
        return cls(raw["collectionGroup"], raw.get("queryScope", "COLLECTION"), fields)

    def serves(self, shape: QueryShape) -> bool:
        if self.collection != shape.collection or self.scope != shape.scope:
            return False
        prefix = shape.equality | shape.array_contains
        orders = shape.effective_orders()
        if len(self.fields) != len(prefix) + len(orders):
            return False
        head, tail = self.fields[: len(prefix)], self.fields[len(prefix) :]
        for path, mode in head:
            if path in shape.array_contains:
                if mode != "CONTAINS":
                    return False
            elif path not in shape.equality or mode not in (ASC, DESC):
                return False
        if {p for p, _ in head} != prefix:
            return False
        return tail == orders


@dataclass
class IndexReport:
    """Queries seen during a run, checked against the declared indexes."""

    indexes: list[Index]
    used: set[Index] = field(default_factory=set)
    missing: dict[QueryShape, str] = field(default_factory=dict)
    unsupported: dict[str, str] = field(default_factory=dict)

    def record(self, query: StructuredQuery, where: str) -> str | None:
        """Check one executed query. Returns an error message if production would reject it."""
        try:
            shape = shape_of(query)
        except UnsupportedQueryError as exc:
            self.unsupported.setdefault(str(exc), where)
            return f"{where}: {exc}"
        if not shape.needs_composite_index():
            return None
        serving = [i for i in self.indexes if i.serves(shape)]
        if serving:
            self.used.update(serving)
            return None
        self.missing.setdefault(shape, where)
        return (
            f"{where}: production Firestore would reject this query (no composite index).\n"
            f"  query: {shape.describe()}\n"
            f"  add to firestore.indexes.json: {json.dumps(shape.suggested_index())}"
        )

    def unused(self) -> list[Index]:
        return [i for i in self.indexes if i not in self.used]


def load_indexes(path: Path = INDEXES_PATH) -> list[Index]:
    raw = json.loads(path.read_text())
    return [Index.from_json(i) for i in raw.get("indexes", [])]


def shape_of(query: StructuredQuery) -> QueryShape:
    if len(query.from_) != 1:
        raise UnsupportedQueryError("query over more than one collection selector")
    selector = query.from_[0]
    equality: set[str] = set()
    array_contains: set[str] = set()
    inequality: set[str] = set()

    def visit(f: StructuredQuery.Filter) -> None:
        kind = StructuredQuery.Filter.pb(f).WhichOneof("filter_type")
        if kind == "composite_filter":
            if f.composite_filter.op != StructuredQuery.CompositeFilter.Operator.AND:
                raise UnsupportedQueryError("OR filter (not modeled; check its indexes by hand)")
            for sub in f.composite_filter.filters:
                visit(sub)
        elif kind == "field_filter":
            path, op = f.field_filter.field.field_path, f.field_filter.op
            if op in _EQUALITY_OPS:
                equality.add(path)
            elif op in _ARRAY_OPS:
                array_contains.add(path)
            elif op in _INEQUALITY_OPS:
                inequality.add(path)
            else:
                raise UnsupportedQueryError(f"field filter operator {op!r}")
        elif kind == "unary_filter":
            path = f.unary_filter.field.field_path
            (equality if f.unary_filter.op in _UNARY_EQUALITY_OPS else inequality).add(path)

    if StructuredQuery.pb(query).HasField("where"):
        visit(query.where)
    orders = tuple(
        (o.field.field_path, ASC if o.direction == _Direction.ASCENDING else DESC)
        for o in query.order_by
    )
    return QueryShape(
        collection=selector.collection_id,
        collection_group=bool(selector.all_descendants),
        equality=frozenset(equality),
        array_contains=frozenset(array_contains),
        inequality=frozenset(inequality - equality),
        orders=orders,
    )
