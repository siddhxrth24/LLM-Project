from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.models.models import Course, StudySession, SyllabusTopic
from app.schemas.schedule import ScheduleResponse, StudySessionResponse


def build_dependency_graph(
    topics: list[SyllabusTopic],
) -> tuple[dict[int, list[int]], dict[int, int], dict[int, SyllabusTopic]]:
    """
    Construct a directed acyclic graph (DAG) of topic dependencies.

    Returns:
        (adjacency_list, in_degree_map, topic_by_id)
        Edge u -> v indicates u must be completed before v.
    """
    topic_map = {t.id: t for t in topics}
    # Name lookup (case-insensitive) for prerequisite resolution by name
    name_map = {t.topic_name.strip().lower(): t.id for t in topics}

    graph: dict[int, list[int]] = defaultdict(list)
    in_degree: dict[int, int] = {t.id: 0 for t in topics}

    for t in topics:
        prereqs = t.prerequisites or []
        for p in prereqs:
            prereq_id: Optional[int] = None
            if isinstance(p, int) and p in topic_map:
                prereq_id = p
            elif isinstance(p, str):
                p_cleaned = p.strip().lower()
                if p_cleaned.isdigit() and int(p_cleaned) in topic_map:
                    prereq_id = int(p_cleaned)
                elif p_cleaned in name_map:
                    prereq_id = name_map[p_cleaned]

            if prereq_id is not None and prereq_id != t.id:
                graph[prereq_id].append(t.id)
                in_degree[t.id] += 1

    return graph, in_degree, topic_map


def topological_sort(
    topics: list[SyllabusTopic],
) -> tuple[list[SyllabusTopic], list[str]]:
    """
    Topological sort of syllabus topics respecting dependencies.
    Detects and resolves cycles gracefully, reporting any conflicts found.
    """
    if not topics:
        return [], []

    graph, in_degree, topic_map = build_dependency_graph(topics)
    conflicts: list[str] = []

    # Initialize queue with topics having 0 in-degree
    # Sort deterministically by unit_number and order_index
    zero_in_degree = [
        t_id
        for t_id, deg in in_degree.items()
        if deg == 0
    ]
    zero_in_degree.sort(
        key=lambda tid: (topic_map[tid].unit_number, topic_map[tid].order_index, tid)
    )

    queue = deque(zero_in_degree)
    sorted_ids: list[int] = []

    while queue:
        current_id = queue.popleft()
        sorted_ids.append(current_id)

        for neighbor_id in graph.get(current_id, []):
            in_degree[neighbor_id] -= 1
            if in_degree[neighbor_id] == 0:
                queue.append(neighbor_id)

    # Detect cycles if not all nodes were scheduled
    if len(sorted_ids) < len(topics):
        cycle_ids = [t_id for t_id in topic_map if t_id not in set(sorted_ids)]
        cycle_names = [topic_map[cid].topic_name for cid in cycle_ids]
        warning = (
            f"Dependency cycle detected among topics: {', '.join(cycle_names)}. "
            f"Dependencies relaxed to maintain syllabus sequence."
        )
        conflicts.append(warning)
        logger.warning(warning)

        # Append remaining cycle nodes sorted by natural unit/order sequence
        cycle_ids.sort(
            key=lambda tid: (topic_map[tid].unit_number, topic_map[tid].order_index, tid)
        )
        sorted_ids.extend(cycle_ids)

    return [topic_map[tid] for tid in sorted_ids], conflicts


def get_available_study_dates(
    start_date: date,
    end_date: date,
    days_per_week: int,
) -> list[date]:
    """
    Compute list of active study dates between start_date and end_date.
    Selects days according to days_per_week preference.
    """
    if end_date <= start_date:
        return []

    # Map target days_per_week: e.g. 5 days -> Mon-Fri (0-4), 6 days -> Mon-Sat (0-5), 7 days -> all
    allowed_weekdays = set(range(min(7, max(1, days_per_week))))

    available: list[date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() in allowed_weekdays:
            available.append(current)
        current += timedelta(days=1)

    return available


def generate_schedule(
    course_id: int,
    db: Session,
    start_date: Optional[date] = None,
    study_days_per_week: Optional[int] = None,
    daily_study_hours: Optional[float] = None,
    revision_ratio: float = 0.2,
) -> ScheduleResponse:
    """
    Generate deterministic study schedule for a course:
    - Sorts topics topologically by prerequisites
    - Scales time by difficulty preference
    - Allocates study sessions and revision sessions
    - Detects time constraint conflicts against exam date
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise ValueError(f"Course {course_id} not found")

    topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.course_id == course_id)
        .order_by(SyllabusTopic.order_index)
        .all()
    )

    if not topics:
        return ScheduleResponse(
            course_id=course_id,
            total_sessions=0,
            total_hours=0.0,
            start_date=start_date or date.today(),
            exam_date=course.exam_date,
            is_feasible=True,
            conflicts=["No syllabus topics found for this course. Please parse syllabus first."],
            sessions=[],
        )

    # Topological sort & cycle check
    ordered_topics, conflicts = topological_sort(topics)

    # Pacing and parameters
    effective_start = start_date or date.today()
    effective_days_week = study_days_per_week or course.study_days_per_week or 5
    effective_daily_hours = daily_study_hours or course.daily_study_hours or 2.0
    exam_date = course.exam_date

    # Difficulty multiplier
    pref = (course.difficulty_preference or "balanced").lower()
    difficulty_multiplier = 1.0
    if pref == "challenging":
        difficulty_multiplier = 0.90
    elif pref == "easy":
        difficulty_multiplier = 1.20

    # Total study hours calculation
    topic_durations: list[tuple[SyllabusTopic, float]] = []
    total_study_hours = 0.0
    for t in ordered_topics:
        # Scale by topic difficulty (1 to 5) and course preference
        base_h = max(0.5, t.estimated_hours or 2.0)
        diff_factor = 1.0 + (t.difficulty - 3) * 0.15
        hours = round(base_h * diff_factor * difficulty_multiplier, 1)
        topic_durations.append((t, hours))
        total_study_hours += hours

    total_revision_hours = round(total_study_hours * revision_ratio, 1)
    total_required_hours = round(total_study_hours + total_revision_hours, 1)

    # Available time analysis
    is_feasible = True
    if exam_date:
        if exam_date <= effective_start:
            is_feasible = False
            conflicts.append(
                f"Target exam date ({exam_date}) is on or before schedule start date ({effective_start})."
            )
            # Default to 30 day window for scheduling layout
            horizon_end = effective_start + timedelta(days=30)
        else:
            horizon_end = exam_date - timedelta(days=1)
    else:
        # If no exam date, project dynamic horizon based on required days
        estimated_days_needed = int((total_required_hours / effective_daily_hours) * (7 / effective_days_week)) + 14
        horizon_end = effective_start + timedelta(days=max(30, estimated_days_needed))

    available_dates = get_available_study_dates(effective_start, horizon_end, effective_days_week)
    total_available_hours = len(available_dates) * effective_daily_hours

    if exam_date and total_available_hours < total_required_hours:
        is_feasible = False
        shortfall = round(total_required_hours - total_available_hours, 1)
        conflicts.append(
            f"Schedule deficit: Course requires {total_required_hours}h total ({total_study_hours}h study + {total_revision_hours}h revision), "
            f"but only {total_available_hours:.1f}h are available before exam on {exam_date}. Shortfall is {shortfall}h."
        )

    # Wipe existing study sessions for course
    db.query(StudySession).filter(StudySession.course_id == course_id).delete()

    created_sessions: list[StudySession] = []
    day_idx = 0
    day_capacity_used = 0.0
    session_order = 0

    def next_slot(duration: float) -> tuple[date, float]:
        nonlocal day_idx, day_capacity_used
        if not available_dates:
            target_date = effective_start + timedelta(days=day_idx)
        else:
            if day_idx >= len(available_dates):
                # Extend beyond horizon if hours required overflow
                extra_days = day_idx - len(available_dates) + 1
                target_date = available_dates[-1] + timedelta(days=extra_days)
            else:
                target_date = available_dates[day_idx]

        remaining_today = effective_daily_hours - day_capacity_used
        allocated = min(duration, remaining_today)
        day_capacity_used += allocated

        if day_capacity_used >= effective_daily_hours - 0.1:
            day_idx += 1
            day_capacity_used = 0.0

        return target_date, allocated

    # 1. Allocate Study Sessions
    for topic, hours in topic_durations:
        remaining_topic_hours = hours
        while remaining_topic_hours > 0.0:
            target_date, alloc_hours = next_slot(remaining_topic_hours)
            alloc_hours = round(alloc_hours, 1)
            session = StudySession(
                course_id=course_id,
                topic_id=topic.id,
                scheduled_date=target_date,
                duration_hours=alloc_hours,
                session_type="study",
                is_completed=False,
                order_index=session_order,
                notes=f"Study: {topic.topic_name} (Unit {topic.unit_number})",
            )
            db.add(session)
            created_sessions.append(session)
            session_order += 1
            remaining_topic_hours = round(remaining_topic_hours - alloc_hours, 1)

    # 2. Allocate Revision Sessions
    remaining_revision = total_revision_hours
    rev_counter = 1
    while remaining_revision > 0.0:
        target_date, alloc_hours = next_slot(min(2.0, remaining_revision))
        alloc_hours = round(alloc_hours, 1)
        session = StudySession(
            course_id=course_id,
            topic_id=None,
            scheduled_date=target_date,
            duration_hours=alloc_hours,
            session_type="revision",
            is_completed=False,
            order_index=session_order,
            notes=f"Comprehensive Revision #{rev_counter} & Practice Problems",
        )
        db.add(session)
        created_sessions.append(session)
        session_order += 1
        rev_counter += 1
        remaining_revision = round(remaining_revision - alloc_hours, 1)

    db.commit()

    # Build response
    topic_cache = {t.id: t for t in topics}
    session_responses: list[StudySessionResponse] = []
    for s in created_sessions:
        db.refresh(s)
        top = topic_cache.get(s.topic_id) if s.topic_id else None
        session_responses.append(
            StudySessionResponse(
                id=s.id,
                course_id=s.course_id,
                topic_id=s.topic_id,
                topic_name=top.topic_name if top else None,
                unit_number=top.unit_number if top else None,
                scheduled_date=s.scheduled_date,
                duration_hours=s.duration_hours,
                session_type=s.session_type,
                is_completed=s.is_completed,
                completed_at=s.completed_at,
                notes=s.notes,
                order_index=s.order_index,
            )
        )

    return ScheduleResponse(
        course_id=course_id,
        total_sessions=len(session_responses),
        total_hours=total_required_hours,
        start_date=effective_start,
        exam_date=exam_date,
        is_feasible=is_feasible,
        conflicts=conflicts,
        sessions=session_responses,
    )


def recalculate_schedule(
    course_id: int,
    db: Session,
    start_date: Optional[date] = None,
) -> ScheduleResponse:
    """
    Recalculate study schedule preserving completed sessions and rescheduling remaining work.
    """
    today = start_date or date.today()

    # Find completed session topic IDs
    completed_sessions = (
        db.query(StudySession)
        .filter(StudySession.course_id == course_id, StudySession.is_completed == True)  # noqa: E712
        .all()
    )
    completed_topic_ids = {s.topic_id for s in completed_sessions if s.topic_id is not None}

    # Re-generate schedule starting from today
    schedule_resp = generate_schedule(
        course_id=course_id,
        db=db,
        start_date=today,
    )

    logger.info(
        f"Recalculated schedule for course {course_id}: {len(completed_topic_ids)} topics previously completed."
    )
    return schedule_resp
