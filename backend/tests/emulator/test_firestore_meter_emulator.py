"""The Firestore meter counts what Firestore would bill, for every kind of call the app makes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from google.cloud.firestore import async_transactional
from google.cloud.firestore_v1 import FieldFilter

from tests.firestore_meter import FirestoreMeter

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient as FirestoreAsyncClient
    from google.cloud.firestore_v1.async_transaction import AsyncTransaction


@pytest.fixture
def meter(db: FirestoreAsyncClient, monkeypatch: pytest.MonkeyPatch) -> FirestoreMeter:
    m = FirestoreMeter()
    m.install(monkeypatch)
    return m


async def _seed(db: FirestoreAsyncClient, n: int) -> None:
    for start in range(0, n, 450):
        batch = db.batch()
        for i in range(start, min(n, start + 450)):
            batch.set(db.collection("things").document(f"t{i:05d}"), {"n": i, "even": i % 2 == 0})
        await batch.commit()


async def test_writes_count_one_per_document(
    db: FirestoreAsyncClient, meter: FirestoreMeter
) -> None:
    await _seed(db, 4)
    await db.collection("things").document("t00000").update({"n": -1})
    await db.collection("things").document("t00001").delete()
    assert meter.usage.writes == 6
    assert meter.usage.reads == 0


async def test_reads_follow_billing_rules(db: FirestoreAsyncClient, meter: FirestoreMeter) -> None:
    await _seed(db, 1500)
    things = db.collection("things")

    def billed(expected_reads: int) -> None:
        assert meter.usage.reads == expected_reads, meter.usage.describe()
        meter.reset()

    meter.reset()
    await things.where(filter=FieldFilter("n", "<", 7)).get()
    billed(7)  # one per document returned

    await things.where(filter=FieldFilter("n", "<", 0)).get()
    billed(1)  # an empty result still costs one

    async for _ in things.where(filter=FieldFilter("n", "<", 3)).stream():
        pass
    billed(3)

    await things.document("t00010").get()
    await things.document("missing").get()
    billed(2)  # one per document requested, found or not

    refs = [things.document(f"t{i:05d}") for i in range(5)] + [things.document("missing")]
    async for _ in db.get_all(refs):
        pass
    billed(6)

    await things.count().get()
    billed(2)  # 1,500 index entries: one read per 1,000, rounded up
    await things.where(filter=FieldFilter("n", "<", 0)).count().get()
    billed(1)

    @async_transactional
    async def bump(txn: AsyncTransaction) -> None:
        snap = await things.document("t00002").get(transaction=txn)
        txn.update(snap.reference, {"n": 99})

    await bump(db.transaction())
    assert (meter.usage.reads, meter.usage.writes) == (1, 1), meter.usage.describe()
    assert meter.usage.by_collection == {"things": 1}
