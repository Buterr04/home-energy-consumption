from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Household, HouseholdProfile, User
from app.security import hash_password

DEMO_HOUSEHOLDS = [94, 435, 466, 496]


def _get_or_create_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str,
    role: str,
) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.display_name = display_name
        user.role = role
        user.is_active = True
    return user


def seed_demo(db: Session) -> dict:
    admin = _get_or_create_user(
        db,
        username="admin",
        password="admin123",
        display_name="Administrator",
        role="admin",
    )
    demo1 = _get_or_create_user(
        db,
        username="demo1",
        password="demo123",
        display_name="Demo 1",
        role="user",
    )
    demo2 = _get_or_create_user(
        db,
        username="demo2",
        password="demo123",
        display_name="Demo 2",
        role="user",
    )

    household_ids = list(
        db.scalars(select(Household.id).order_by(Household.id)).all()
    )
    if not household_ids:
        db.commit()
        return {
            "users": ["admin", "demo1", "demo2"],
            "demo1": [],
            "demo2": [],
            "note": "No households found. Import the CSV before seeding.",
        }

    for household in db.scalars(select(Household)).all():
        household.owner_user_id = None

    temps = dict(
        db.execute(
            select(
                HouseholdProfile.household_id,
                HouseholdProfile.avg_temp_c,
            )
        ).all()
    )
    ordered = sorted(
        household_ids,
        key=lambda household_id: (
            temps.get(household_id) is None,
            temps.get(household_id) or 0.0,
            household_id,
        ),
    )
    bucket_size = max(1, len(ordered) // 5)
    buckets = [
        ordered[index * bucket_size : (index + 1) * bucket_size]
        for index in range(5)
    ]
    buckets[-1].extend(ordered[bucket_size * 5 :])

    preferred = [
        household_id
        for household_id in DEMO_HOUSEHOLDS
        if household_id in household_ids
    ]
    demo1_ids: list[int] = []
    selected_buckets: set[int] = set()
    for household_id in preferred:
        bucket_index = next(
            (
                index
                for index, bucket in enumerate(buckets)
                if household_id in bucket
            ),
            None,
        )
        if bucket_index is not None and bucket_index not in selected_buckets:
            demo1_ids.append(household_id)
            selected_buckets.add(bucket_index)
    for index, bucket in enumerate(buckets):
        if len(demo1_ids) >= 5:
            break
        if index in selected_buckets:
            continue
        candidate = next(
            (
                household_id
                for household_id in bucket
                if household_id not in demo1_ids
            ),
            None,
        )
        if candidate is not None:
            demo1_ids.append(candidate)
    if len(demo1_ids) < 5:
        demo1_ids.extend(
            household_id
            for household_id in household_ids
            if household_id not in demo1_ids
        )
        demo1_ids = demo1_ids[:5]

    owned = set(demo1_ids)
    demo2_ids: list[int] = []
    by_bucket: dict[int, list[int]] = defaultdict(list)
    for index, bucket in enumerate(buckets):
        for household_id in bucket:
            if household_id not in owned:
                by_bucket[index].append(household_id)
    for index in range(5):
        candidates = by_bucket.get(index, [])
        if candidates:
            demo2_ids.append(candidates[0])
    if len(demo2_ids) < 5:
        demo2_ids.extend(
            household_id
            for household_id in household_ids
            if household_id not in owned and household_id not in demo2_ids
        )
        demo2_ids = demo2_ids[:5]

    for household in db.scalars(
        select(Household).where(Household.id.in_(demo1_ids))
    ).all():
        household.owner_user_id = demo1.id
    for household in db.scalars(
        select(Household).where(Household.id.in_(demo2_ids))
    ).all():
        household.owner_user_id = demo2.id

    db.commit()
    return {
        "users": [
            {"username": "admin", "password": "admin123"},
            {"username": "demo1", "password": "demo123"},
            {"username": "demo2", "password": "demo123"},
        ],
        "demo1": demo1_ids,
        "demo2": demo2_ids,
        "admin_user_id": admin.id,
    }
