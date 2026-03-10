"""Tests for memory namespace helpers."""

from agent.memory.namespaces import (
    PROFILE_KEY,
    global_memories_ns,
    profile_ns,
    project_memories_ns,
)


def test_profile_namespace():
    assert profile_ns("learner-1") == ("learner-1", "profile")


def test_global_memories_namespace():
    assert global_memories_ns("learner-1") == ("learner-1", "memories")


def test_project_memories_namespace():
    ns = project_memories_ns("learner-1", "maji-ndogo-part1")
    assert ns == ("learner-1", "maji-ndogo-part1", "memories")


def test_profile_key():
    assert PROFILE_KEY == "main"


def test_different_learners_different_namespaces():
    assert profile_ns("learner-1") != profile_ns("learner-2")
    assert global_memories_ns("learner-1") != global_memories_ns("learner-2")


def test_different_projects_different_namespaces():
    ns_a = project_memories_ns("learner-1", "project-a")
    ns_b = project_memories_ns("learner-1", "project-b")
    assert ns_a != ns_b
