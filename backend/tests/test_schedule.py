from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.models import Course, SyllabusTopic
from app.services.schedule_service import (
    build_dependency_graph,
    generate_schedule,
    topological_sort,
)


def test_dependency_graph_building() -> None:
    """Verify directed graph edges and in-degree computation."""
    t1 = SyllabusTopic(id=1, topic_name="CPU Scheduling", prerequisites=[], unit_number=1, order_index=0)
    t2 = SyllabusTopic(id=2, topic_name="Deadlocks", prerequisites=[1], unit_number=1, order_index=1)
    t3 = SyllabusTopic(id=3, topic_name="Banker Algorithm", prerequisites=[2], unit_number=1, order_index=2)

    graph, in_degree, topic_map = build_dependency_graph([t1, t2, t3])

    assert 2 in graph[1]
    assert 3 in graph[2]
    assert in_degree[1] == 0
    assert in_degree[2] == 1
    assert in_degree[3] == 1


def test_topological_sort_linear() -> None:
    """Verify correct linear ordering when dependencies are well-formed."""
    t1 = SyllabusTopic(id=10, topic_name="Basics", prerequisites=[], unit_number=1, order_index=0)
    t2 = SyllabusTopic(id=20, topic_name="Intermediate", prerequisites=[10], unit_number=1, order_index=1)
    t3 = SyllabusTopic(id=30, topic_name="Advanced", prerequisites=[20], unit_number=1, order_index=2)

    sorted_topics, conflicts = topological_sort([t3, t1, t2])
    assert len(conflicts) == 0
    assert [t.id for t in sorted_topics] == [10, 20, 30]


def test_cycle_detection_and_conflict_reporting() -> None:
    """Verify cyclic prerequisite detection and graceful resolution."""
    t_a = SyllabusTopic(id=101, topic_name="Recursion", prerequisites=[102], unit_number=1, order_index=0)
    t_b = SyllabusTopic(id=102, topic_name="Induction", prerequisites=[101], unit_number=1, order_index=1)

    sorted_topics, conflicts = topological_sort([t_a, t_b])

    # Should report conflict without crashing
    assert len(conflicts) > 0
    assert any("cycle" in c.lower() for c in conflicts)
    # Both topics must still be included in output
    assert len(sorted_topics) == 2


def test_schedule_generation_and_time_allocation(db_session: Session, test_course: Course) -> None:
    """Verify schedule generator produces study & revision sessions."""
    # Add topics to test course
    t1 = SyllabusTopic(
        course_id=test_course.id,
        unit_number=1,
        topic_name="Processes & Threads",
        estimated_hours=2.0,
        difficulty=3,
        prerequisites=[],
    )
    t2 = SyllabusTopic(
        course_id=test_course.id,
        unit_number=1,
        topic_name="Semaphores & Mutex",
        estimated_hours=3.0,
        difficulty=4,
        prerequisites=[],
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # Generate schedule
    resp = generate_schedule(
        course_id=test_course.id,
        db=db_session,
        start_date=date.today(),
        study_days_per_week=5,
        daily_study_hours=2.0,
        revision_ratio=0.2,
    )

    assert resp.total_sessions > 0
    assert resp.total_hours > 0
    # Should include both study and revision sessions
    session_types = {s.session_type for s in resp.sessions}
    assert "study" in session_types
    assert "revision" in session_types


def test_constraint_conflict_reporting(db_session: Session) -> None:
    """Verify infeasible exam deadlines trigger constraint warnings."""
    # Exam date is tomorrow, but requires 30 hours of study
    past_due_course = Course(
        name="Urgent Exam Cram",
        exam_date=date.today() + timedelta(days=1),
        study_days_per_week=5,
        daily_study_hours=2.0,
    )
    db_session.add(past_due_course)
    db_session.commit()
    db_session.refresh(past_due_course)

    for i in range(10):
        topic = SyllabusTopic(
            course_id=past_due_course.id,
            unit_number=1,
            topic_name=f"Big Topic {i}",
            estimated_hours=4.0,
            difficulty=5,
        )
        db_session.add(topic)
    db_session.commit()

    resp = generate_schedule(
        course_id=past_due_course.id,
        db=db_session,
        start_date=date.today(),
    )

    assert resp.is_feasible is False
    assert len(resp.conflicts) > 0
    assert any("deficit" in c.lower() or "requires" in c.lower() for c in resp.conflicts)
