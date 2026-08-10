from __future__ import annotations

from app.features.activities.models import Activity, TimeBlock

# Nine Predefined Static Activities per SPEC §5.1 & §9.5
PREDEFINED_ACTIVITIES: list[Activity] = [
    Activity(
        id="running",
        name="Outdoor / Treadmill Run",
        category="cardio",
        tracker="apple_fitness",
        min_duration_seconds=300,  # 5 mins
        max_duration_seconds=14400,  # 4 hours
        default_duration_seconds=1800,  # 30 mins
        icon_name="run",
        is_active=True,
    ),
    Activity(
        id="cycling",
        name="Cycling / Spin Workout",
        category="cardio",
        tracker="apple_fitness",
        min_duration_seconds=300,  # 5 mins
        max_duration_seconds=14400,  # 4 hours
        default_duration_seconds=2700,  # 45 mins
        icon_name="bike",
        is_active=True,
    ),
    Activity(
        id="strength",
        name="Strength Training",
        category="workout",
        tracker="apple_fitness",
        min_duration_seconds=600,  # 10 mins
        max_duration_seconds=7200,  # 2 hours
        default_duration_seconds=2700,  # 45 mins
        icon_name="dumbbell",
        is_active=True,
    ),
    Activity(
        id="yoga",
        name="Yoga & Stretching",
        category="flexibility",
        tracker="youtube",
        min_duration_seconds=300,  # 5 mins
        max_duration_seconds=5400,  # 90 mins
        default_duration_seconds=1800,  # 30 mins
        icon_name="yoga",
        is_active=True,
    ),
    Activity(
        id="pilates",
        name="Pilates Session",
        category="flexibility",
        tracker="youtube",
        min_duration_seconds=300,  # 5 mins
        max_duration_seconds=5400,  # 90 mins
        default_duration_seconds=1800,  # 30 mins
        icon_name="mat",
        is_active=True,
    ),
    Activity(
        id="hiit",
        name="HIIT Workout",
        category="workout",
        tracker="youtube",
        min_duration_seconds=300,  # 5 mins
        max_duration_seconds=3600,  # 60 mins
        default_duration_seconds=1200,  # 20 mins
        icon_name="lightning",
        is_active=True,
    ),
    Activity(
        id="walking",
        name="Walking / Power Walk",
        category="cardio",
        tracker="apple_fitness",
        min_duration_seconds=300,  # 5 mins
        max_duration_seconds=14400,  # 4 hours
        default_duration_seconds=1800,  # 30 mins
        icon_name="walk",
        is_active=True,
    ),
    Activity(
        id="rowing",
        name="Rowing Machine",
        category="cardio",
        tracker="apple_fitness",
        min_duration_seconds=300,  # 5 mins
        max_duration_seconds=7200,  # 2 hours
        default_duration_seconds=1200,  # 20 mins
        icon_name="row",
        is_active=True,
    ),
    Activity(
        id="meditation",
        name="Mindfulness & Meditation",
        category="mindfulness",
        tracker="spotify",
        min_duration_seconds=180,  # 3 mins
        max_duration_seconds=3600,  # 60 mins
        default_duration_seconds=600,  # 10 mins
        icon_name="lotus",
        is_active=True,
    ),
]

# Seven Predefined Time Blocks per SPEC §5.3
PREDEFINED_TIME_BLOCKS: list[TimeBlock] = [
    TimeBlock(
        id="tb_15m",
        label="15 min",
        duration_seconds=900,
        description="Quick micro-session",
    ),
    TimeBlock(
        id="tb_20m",
        label="20 min",
        duration_seconds=1200,
        description="Short workout or focal block",
    ),
    TimeBlock(
        id="tb_30m",
        label="30 min",
        duration_seconds=1800,
        description="Standard active time-box",
    ),
    TimeBlock(
        id="tb_45m",
        label="45 min",
        duration_seconds=2700,
        description="Full training session",
    ),
    TimeBlock(
        id="tb_60m",
        label="60 min",
        duration_seconds=3600,
        description="Hour-long deep session",
    ),
    TimeBlock(
        id="tb_75m",
        label="75 min",
        duration_seconds=4500,
        description="Extended workout block",
    ),
    TimeBlock(
        id="tb_90m",
        label="90 min",
        duration_seconds=5400,
        description="Maximal time-boxing block",
    ),
]


def get_all_activities() -> list[Activity]:
    """Return all predefined activities."""
    return list(PREDEFINED_ACTIVITIES)


def get_activity_by_id(activity_id: str) -> Activity | None:
    """Lookup an activity by its ID."""
    for act in PREDEFINED_ACTIVITIES:
        if act.id == activity_id:
            return act
    return None


def get_all_time_blocks() -> list[TimeBlock]:
    """Return all predefined time blocks."""
    return list(PREDEFINED_TIME_BLOCKS)


def validate_activity_duration(activity_id: str, duration_seconds: int) -> bool:
    """Validate whether duration_seconds falls within sane min/max bounds for the activity."""
    act = get_activity_by_id(activity_id)
    if not act:
        return False
    return act.min_duration_seconds <= duration_seconds <= act.max_duration_seconds
