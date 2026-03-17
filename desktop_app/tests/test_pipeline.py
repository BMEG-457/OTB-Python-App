"""Tests for app/processing/pipeline.py"""

import numpy as np
import pytest
from app.processing.pipeline import ProcessingPipeline, get_pipeline, clear_pipelines


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset global pipeline registry before and after each test."""
    clear_pipelines()
    yield
    clear_pipelines()


class TestProcessingPipeline:
    def test_empty_pipeline_is_identity(self):
        p = ProcessingPipeline()
        data = np.array([1.0, 2.0, 3.0])
        result = p.run(data)
        np.testing.assert_array_equal(result, data)

    def test_single_stage(self):
        p = ProcessingPipeline()
        p.add_stage(lambda x: x * 2)
        data = np.array([1.0, 2.0])
        np.testing.assert_array_equal(p.run(data), np.array([2.0, 4.0]))

    def test_multiple_stages_applied_in_order(self):
        p = ProcessingPipeline()
        p.add_stage(lambda x: x + 1)   # [1,2,3] → [2,3,4]
        p.add_stage(lambda x: x * 2)   # [2,3,4] → [4,6,8]
        data = np.array([1.0, 2.0, 3.0])
        np.testing.assert_array_equal(p.run(data), np.array([4.0, 6.0, 8.0]))

    def test_stages_list_grows_on_add(self):
        p = ProcessingPipeline()
        assert len(p.stages) == 0
        p.add_stage(lambda x: x)
        assert len(p.stages) == 1
        p.add_stage(lambda x: x)
        assert len(p.stages) == 2


class TestGetPipeline:
    def test_returns_pipeline_instance(self):
        p = get_pipeline("test")
        assert isinstance(p, ProcessingPipeline)

    def test_same_name_returns_same_instance(self):
        a = get_pipeline("shared")
        b = get_pipeline("shared")
        assert a is b

    def test_different_names_return_different_instances(self):
        a = get_pipeline("alpha")
        b = get_pipeline("beta")
        assert a is not b

    def test_stages_persist_across_calls(self):
        get_pipeline("persist").add_stage(lambda x: x * 3)
        p = get_pipeline("persist")
        assert len(p.stages) == 1
        np.testing.assert_array_equal(p.run(np.array([2.0])), np.array([6.0]))


class TestClearPipelines:
    def test_clear_removes_all_pipelines(self):
        get_pipeline("a")
        get_pipeline("b")
        clear_pipelines()
        # After clearing, get_pipeline should create a fresh (empty) instance.
        p = get_pipeline("a")
        assert len(p.stages) == 0

    def test_cleared_pipeline_is_new_object(self):
        original = get_pipeline("x")
        clear_pipelines()
        fresh = get_pipeline("x")
        assert original is not fresh
