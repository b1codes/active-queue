from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.core.config import settings
from app.core.firestore import close_firestore, get_firestore_client, init_firestore
from app.core.security import init_firebase_admin
from app.features.content.models import ContentCacheItem, FeedItem, Source
from app.features.sessions.models import Session
from app.features.users.models import User, UserAuthorization, UserPreferences

logger = structlog.get_logger(__name__)

# Workout title templates cycled to build a large, varied fixture catalog
WORKOUT_TYPE_NAMES: list[str] = [
    "Morning Energy HIIT Workout",
    "Full Body Dumbbell Strength",
    "Cardio Treadmill Run Coaching",
    "Spin / Cycling Interval",
    "Post-Workout Yoga & Mobility Routine",
    "Endurance Row & Core Challenge",
    "Quick Core & Abs Blast",
    "Power Pilates Flow",
    "Upper Body Hypertrophy Lifting",
    "Guided Breathing & Mindful Recovery",
    "Bodyweight Calisthenics Routine",
    "Low Impact Cardio Walk",
    "Kettlebell Swings & Conditioning",
    "Zone 2 Outdoor Run Companion",
    "Hamstring & Hip Flexor Stretch",
    "Boxing Cardio Combo Circuit",
    "Barre Sculpt & Tone Session",
    "Trail Run Interval Coaching",
    "Deadlift & Squat Technique Clinic",
    "Guided Meditation & Breathwork",
]

# Durations span every activity's min/max range (5 min - 90 min) per activities/catalog.py
DURATION_VARIANTS_SECONDS: list[int] = [
    300,
    600,
    900,
    1200,
    1500,
    1800,
    2100,
    2400,
    2700,
    3000,
    3300,
    3600,
    3900,
    4200,
    4500,
    4800,
    5100,
    5400,
]


def _build_workout_catalog(count: int) -> list[dict[str, Any]]:
    """Deterministically generate `count` fixture workout items spanning a wide duration range."""
    items: list[dict[str, Any]] = []
    for idx in range(count):
        type_name = WORKOUT_TYPE_NAMES[idx % len(WORKOUT_TYPE_NAMES)]
        duration = DURATION_VARIANTS_SECONDS[idx % len(DURATION_VARIANTS_SECONDS)]
        minutes = duration // 60
        items.append(
            {
                "external_id": f"fx_vid_{idx + 1:04d}",
                "title": f"{minutes}-Min {type_name}",
                "duration_seconds": duration,
            }
        )
    return items


# Sample workout content items for fixture database seeding.
# 80 items ensures the queue feed spans multiple pagination pages (20/page)
# and every duration preset / activity range has matching content.
SAMPLE_WORKOUT_ITEMS: list[dict[str, Any]] = _build_workout_catalog(80)

# Every 7th item (by catalog index) is marked consumed for the primary user,
# leaving a large majority unconsumed so the feed page can paginate.
PRIMARY_CONSUMED_INDICES: set[int] = set(range(0, len(SAMPLE_WORKOUT_ITEMS), 7))

# Demo user only gets the first N catalog items, with every 4th marked consumed.
DEMO_FEED_ITEM_COUNT = 20
DEMO_CONSUMED_INDICES: set[int] = set(range(0, DEMO_FEED_ITEM_COUNT, 4))


async def seed_firebase_auth(users: list[dict[str, str]], quiet: bool = False) -> int:
    """Create or update test users in the Firebase Auth emulator."""
    init_firebase_admin(settings)
    from firebase_admin import auth

    seeded_count = 0
    for user_info in users:
        target_uid = user_info["uid"]
        email = user_info["email"]
        display_name = user_info["display_name"]
        password = user_info.get("password", "password123")

        try:
            # Delete any existing user with the same email if UID doesn't match target_uid
            # (e.g. created by client-side createUserWithEmailAndPassword with random UID)
            try:
                existing_by_email = auth.get_user_by_email(email)
                if existing_by_email.uid != target_uid:
                    auth.delete_user(existing_by_email.uid)
                    if not quiet:
                        print(
                            f"  🗑 Deleted stale Auth user with auto-generated UID ({existing_by_email.uid})"
                        )
            except auth.UserNotFoundError:
                pass

            # Check if user with target_uid exists
            try:
                auth.get_user(target_uid)
                auth.update_user(
                    target_uid,
                    email=email,
                    display_name=display_name,
                    password=password,
                )
                if not quiet:
                    print(f"  ✓ Updated Firebase Auth user: {display_name} ({target_uid})")
            except auth.UserNotFoundError:
                auth.create_user(
                    uid=target_uid,
                    email=email,
                    display_name=display_name,
                    password=password,
                    email_verified=True,
                )
                if not quiet:
                    print(f"  ✓ Created Firebase Auth user: {display_name} ({target_uid})")

            seeded_count += 1
        except Exception as err:
            logger.warning("firebase_auth_seed_failed", uid=target_uid, error=str(err))
            if not quiet:
                print(f"  ⚠ Failed to seed Auth user {target_uid}: {err}")

    return seeded_count


async def clear_collections(db: Any, quiet: bool = False) -> None:
    """Clear test data from Firestore collections."""
    collections = [
        "users",
        "user_authorization",
        "sources",
        "content_cache",
        "feed_items",
        "sessions",
    ]
    if not quiet:
        print("🧹 Clearing existing test data from Firestore collections...")

    for col_name in collections:
        docs = await db.collection(col_name).get()
        if docs:
            batch = db.batch()
            for doc in docs:
                batch.delete(doc.reference)
            await batch.commit()
            if not quiet:
                print(f"  - Deleted {len(docs)} document(s) from {col_name}")


async def seed_db(
    clear: bool = False,
    primary_user_id: str = "test-user-123",
    quiet: bool = False,
) -> dict[str, int]:
    """Execute local database seeding logic for testing."""
    await init_firestore(settings)
    db = get_firestore_client()

    if clear:
        await clear_collections(db, quiet=quiet)

    now = datetime.now(UTC)

    # 1. Define Users & Authorizations
    primary_user = User(
        uid=primary_user_id,
        email="test@activequeue.dev",
        display_name="Test Athlete",
        photo_url="https://api.dicebear.com/7.x/avataaars/svg?seed=test-athlete",
        created_at=now - timedelta(days=30),
        updated_at=now,
        preferences=UserPreferences(
            preferred_activity_types=["running", "cycling", "strength", "hiit", "yoga"],
            preferred_tracker_app="apple_fitness",
            default_time_block_seconds=2700,
            hide_completed=False,
            dark_mode=True,
            sync_enabled=True,
            notifications_enabled=True,
        ),
        consumed_content_ids=[
            f"fx:{SAMPLE_WORKOUT_ITEMS[i]['external_id']}" for i in sorted(PRIMARY_CONSUMED_INDICES)
        ],
    )

    primary_auth = UserAuthorization(
        uid=primary_user_id,
        role="admin",
        status="active",
        disabled=False,
        scopes=["read", "write"],
        created_at=now - timedelta(days=30),
        updated_at=now,
    )

    demo_user = User(
        uid="demo-user-456",
        email="demo@activequeue.app",
        display_name="Demo User",
        photo_url="https://api.dicebear.com/7.x/avataaars/svg?seed=demo-user",
        created_at=now - timedelta(days=7),
        updated_at=now,
        preferences=UserPreferences(
            preferred_activity_types=["running", "walking", "meditation"],
            preferred_tracker_app="youtube",
            default_time_block_seconds=1800,
            hide_completed=False,
            dark_mode=True,
            sync_enabled=True,
            notifications_enabled=True,
        ),
        consumed_content_ids=[
            f"fx:{SAMPLE_WORKOUT_ITEMS[i]['external_id']}" for i in sorted(DEMO_CONSUMED_INDICES)
        ],
    )

    demo_auth = UserAuthorization(
        uid="demo-user-456",
        role="user",
        status="active",
        disabled=False,
        scopes=["read", "write"],
        created_at=now - timedelta(days=7),
        updated_at=now,
    )

    users_list = [primary_user, demo_user]
    auths_list = [primary_auth, demo_auth]

    # Save Users & Authorizations
    batch_users = db.batch()
    for u in users_list:
        batch_users.set(db.collection("users").document(u.uid), u.to_firestore())
    for a in auths_list:
        batch_users.set(db.collection("user_authorization").document(a.uid), a.to_firestore())
    await batch_users.commit()

    # Seed Auth emulator
    if not quiet:
        print("\n🔑 Seeding Firebase Auth emulator...")
    auth_users_info = [
        {
            "uid": primary_user.uid,
            "email": primary_user.email,
            "display_name": primary_user.display_name,
        },
        {
            "uid": demo_user.uid,
            "email": demo_user.email,
            "display_name": demo_user.display_name,
        },
    ]
    auth_count = await seed_firebase_auth(auth_users_info, quiet=quiet)

    # 2. Seed Sources
    source_small = Source(
        id=f"{primary_user_id}_fixture_fixture-small-playlist",
        user_id=primary_user_id,
        provider="fixture",
        external_source_id="fixture-small-playlist",
        title="Fixture Fitness Playlist",
        description=f"A fixture playlist with {len(SAMPLE_WORKOUT_ITEMS)} workout videos",
        item_count=len(SAMPLE_WORKOUT_ITEMS),
        thumbnail_url="https://img.youtube.com/vi/fx_vid_0001/hqdefault.jpg",
        status="active",
        last_sync_at=now,
        created_at=now - timedelta(days=15),
        updated_at=now,
    )

    source_large = Source(
        id=f"{primary_user_id}_fixture_fixture-large-playlist",
        user_id=primary_user_id,
        provider="fixture",
        external_source_id="fixture-large-playlist",
        title="Large Fixture Fitness Playlist (1,200 videos)",
        description="A comprehensive fixture corpus playlist for testing chunked resumable sync",
        item_count=1200,
        thumbnail_url="https://img.youtube.com/vi/fx_vid_0001/hqdefault.jpg",
        status="active",
        last_sync_at=now,
        created_at=now - timedelta(days=15),
        updated_at=now,
    )

    demo_source = Source(
        id="demo-user-456_fixture_fixture-demo-playlist",
        user_id="demo-user-456",
        provider="fixture",
        external_source_id="fixture-demo-playlist",
        title="Demo Wellness Playlist",
        description=f"A smaller fixture playlist with {DEMO_FEED_ITEM_COUNT} workout videos for the demo account",
        item_count=DEMO_FEED_ITEM_COUNT,
        thumbnail_url="https://img.youtube.com/vi/fx_vid_0001/hqdefault.jpg",
        status="active",
        last_sync_at=now,
        created_at=now - timedelta(days=5),
        updated_at=now,
    )

    batch_sources = db.batch()
    batch_sources.set(
        db.collection("sources").document(source_small.id), source_small.to_firestore()
    )
    batch_sources.set(
        db.collection("sources").document(source_large.id), source_large.to_firestore()
    )
    batch_sources.set(
        db.collection("sources").document(demo_source.id), demo_source.to_firestore()
    )
    await batch_sources.commit()

    # 3. Seed Content Cache Items
    content_items: list[ContentCacheItem] = []
    base_pub_time = now - timedelta(days=48)

    for idx, item in enumerate(SAMPLE_WORKOUT_ITEMS):
        ext_id = str(item["external_id"])
        cid = f"fx:{ext_id}"
        c_item = ContentCacheItem(
            content_id=cid,
            provider="fixture",
            external_id=ext_id,
            title=str(item["title"]),
            duration_seconds=int(item["duration_seconds"]),
            published_at=base_pub_time + timedelta(hours=idx * 14.4),
            thumbnail_url=f"https://img.youtube.com/vi/{ext_id}/hqdefault.jpg",
            video_url=f"https://www.youtube.com/watch?v={ext_id}",
            is_available=True,
            created_at=now - timedelta(days=10),
            updated_at=now,
        )
        content_items.append(c_item)

    batch_content = db.batch()
    for c_item in content_items:
        batch_content.set(
            db.collection("content_cache").document(c_item.content_id), c_item.to_firestore()
        )
    await batch_content.commit()

    # 4. Seed Feed Items — primary user gets the full catalog, demo user gets a smaller slice
    feed_items: list[FeedItem] = []
    for idx, c_item in enumerate(content_items):
        feed_item = FeedItem(
            id=f"{primary_user_id}_{c_item.content_id}",
            user_id=primary_user_id,
            content_id=c_item.content_id,
            source_id=source_small.id,
            published_at=c_item.published_at,
            duration_seconds=c_item.duration_seconds,
            consumed=idx in PRIMARY_CONSUMED_INDICES,
            created_at=now - timedelta(days=5),
            updated_at=now,
        )
        feed_items.append(feed_item)

    for idx, c_item in enumerate(content_items[:DEMO_FEED_ITEM_COUNT]):
        feed_item = FeedItem(
            id=f"demo-user-456_{c_item.content_id}",
            user_id="demo-user-456",
            content_id=c_item.content_id,
            source_id=demo_source.id,
            published_at=c_item.published_at,
            duration_seconds=c_item.duration_seconds,
            consumed=idx in DEMO_CONSUMED_INDICES,
            created_at=now - timedelta(days=5),
            updated_at=now,
        )
        feed_items.append(feed_item)

    # Firestore batches cap at 500 writes; chunk defensively even though we're well under that.
    for chunk_start in range(0, len(feed_items), 400):
        batch_feed = db.batch()
        for f_item in feed_items[chunk_start : chunk_start + 400]:
            batch_feed.set(
                db.collection("feed_items").document(f_item.id), f_item.to_firestore()
            )
        await batch_feed.commit()

    # 5. Seed Workout Sessions — a wide spread of statuses, activities, and dates for history/queue testing
    sessions_list = [
        # Completed sessions, oldest to most recent
        Session(
            id="session_seed_completed_01",
            user_id=primary_user_id,
            activity_id="running",
            match_mode="content_first",
            content_id="fx:fx_vid_0006",  # 1800s
            duration_seconds=1800,
            status="completed",
            checklist_completed=True,
            started_at=now - timedelta(days=14),
            completed_at=now - timedelta(days=14) + timedelta(minutes=30),
            created_at=now - timedelta(days=14),
            updated_at=now - timedelta(days=14) + timedelta(minutes=30),
        ),
        Session(
            id="session_seed_completed_02",
            user_id=primary_user_id,
            activity_id="strength",
            match_mode="time_first",
            content_id="fx:fx_vid_0004",  # 1200s
            duration_seconds=1200,
            status="completed",
            checklist_completed=True,
            started_at=now - timedelta(days=12),
            completed_at=now - timedelta(days=12) + timedelta(minutes=20),
            created_at=now - timedelta(days=12),
            updated_at=now - timedelta(days=12) + timedelta(minutes=20),
        ),
        Session(
            id="session_seed_completed_03",
            user_id=primary_user_id,
            activity_id="hiit",
            match_mode="content_first",
            content_id="fx:fx_vid_0003",  # 900s
            duration_seconds=900,
            status="completed",
            checklist_completed=True,
            started_at=now - timedelta(days=9),
            completed_at=now - timedelta(days=9) + timedelta(minutes=15),
            created_at=now - timedelta(days=9),
            updated_at=now - timedelta(days=9) + timedelta(minutes=15),
        ),
        Session(
            id="session_seed_completed_04",
            user_id=primary_user_id,
            activity_id="cycling",
            match_mode="time_first",
            content_id="fx:fx_vid_0009",  # 2700s
            duration_seconds=2700,
            status="completed",
            checklist_completed=True,
            started_at=now - timedelta(days=7),
            completed_at=now - timedelta(days=7) + timedelta(minutes=45),
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(days=7) + timedelta(minutes=45),
        ),
        Session(
            id="session_seed_completed_05",
            user_id=primary_user_id,
            activity_id="rowing",
            match_mode="content_first",
            content_id="fx:fx_vid_0012",  # 3600s
            duration_seconds=3600,
            status="completed",
            checklist_completed=True,
            started_at=now - timedelta(days=5),
            completed_at=now - timedelta(days=5) + timedelta(minutes=60),
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5) + timedelta(minutes=60),
        ),
        Session(
            id="session_seed_completed_06",
            user_id=primary_user_id,
            activity_id="meditation",
            match_mode="time_first",
            content_id="fx:fx_vid_0002",  # 600s
            duration_seconds=600,
            status="completed",
            checklist_completed=True,
            started_at=now - timedelta(days=3),
            completed_at=now - timedelta(days=3) + timedelta(minutes=10),
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3) + timedelta(minutes=10),
        ),
        # Abandoned session — user bailed partway through
        Session(
            id="session_seed_abandoned_01",
            user_id=primary_user_id,
            activity_id="yoga",
            match_mode="content_first",
            content_id="fx:fx_vid_0018",  # 5400s
            duration_seconds=5400,
            status="abandoned",
            checklist_completed=False,
            started_at=now - timedelta(days=2),
            completed_at=None,
            abandoned_at=now - timedelta(days=2) + timedelta(minutes=8),
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2) + timedelta(minutes=8),
        ),
        # In-progress session — feeds the active session banner on the queue screen
        Session(
            id="session_seed_in_progress_01",
            user_id=primary_user_id,
            activity_id="walking",
            match_mode="content_first",
            content_id="fx:fx_vid_0011",  # 3300s
            duration_seconds=3300,
            status="in_progress",
            checklist_completed=False,
            started_at=now - timedelta(minutes=15),
            completed_at=None,
            created_at=now - timedelta(minutes=15),
            updated_at=now - timedelta(minutes=15),
        ),
        # Pending sessions — not yet started
        Session(
            id="session_seed_pending_01",
            user_id=primary_user_id,
            activity_id="pilates",
            match_mode="time_first",
            content_id="fx:fx_vid_0008",  # 2400s
            duration_seconds=2400,
            status="pending",
            checklist_completed=False,
            started_at=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        ),
        Session(
            id="session_seed_pending_02",
            user_id=primary_user_id,
            activity_id="hiit",
            match_mode="content_first",
            content_id="fx:fx_vid_0005",  # 1500s
            duration_seconds=1500,
            status="pending",
            checklist_completed=False,
            started_at=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        ),
        # Demo user sessions
        Session(
            id="session_seed_demo_completed_01",
            user_id="demo-user-456",
            activity_id="walking",
            match_mode="content_first",
            content_id="fx:fx_vid_0001",  # 300s
            duration_seconds=300,
            status="completed",
            checklist_completed=True,
            started_at=now - timedelta(days=4),
            completed_at=now - timedelta(days=4) + timedelta(minutes=5),
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(days=4) + timedelta(minutes=5),
        ),
        Session(
            id="session_seed_demo_pending_01",
            user_id="demo-user-456",
            activity_id="meditation",
            match_mode="time_first",
            content_id="fx:fx_vid_0002",  # 600s
            duration_seconds=600,
            status="pending",
            checklist_completed=False,
            started_at=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        ),
    ]

    batch_sessions = db.batch()
    for s in sessions_list:
        batch_sessions.set(db.collection("sessions").document(s.id), s.to_firestore())
    await batch_sessions.commit()

    await close_firestore()

    counts = {
        "users": len(users_list),
        "authorizations": len(auths_list),
        "auth_emulator_users": auth_count,
        "sources": 3,
        "content_cache": len(content_items),
        "feed_items": len(feed_items),
        "sessions": len(sessions_list),
    }

    if not quiet:
        print("\n✨ Database seeding completed successfully!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  👤 Users created/seeded:         {counts['users']}")
        print(f"  🛡️ Authorizations created:       {counts['authorizations']}")
        print(f"  🔑 Auth Emulator Users seeded:   {counts['auth_emulator_users']}")
        print(f"  📺 Sources created:               {counts['sources']}")
        print(f"  📼 Content Cache Items seeded:    {counts['content_cache']}")
        print(f"  📰 Feed Items seeded:            {counts['feed_items']}")
        print(f"  🏋️ Sessions seeded:              {counts['sessions']}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  Primary Test User UID: {primary_user_id}")
        print("  Primary Test Email:    test@activequeue.dev")
        print("  Password:              password123\n")

    return counts


def main() -> None:
    """CLI entrypoint for seed command."""
    parser = argparse.ArgumentParser(
        description="ActiveQueue Database Seeder — Seed local Firestore and Auth emulators with mock test data."
    )
    parser.add_argument(
        "--clear",
        "-c",
        action="store_true",
        help="Clear existing seed collections before seeding data.",
    )
    parser.add_argument(
        "--user-id",
        "-u",
        default="test-user-123",
        help="Primary test user ID (default: test-user-123).",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output summary.",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            seed_db(
                clear=args.clear,
                primary_user_id=args.user_id,
                quiet=args.quiet,
            )
        )
    except Exception as err:
        print(f"\n❌ Error during database seeding: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
