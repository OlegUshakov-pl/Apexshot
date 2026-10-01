from __future__ import annotations

import json

import pytest

from app.default_prompts import BASE_SYSTEM_PROMPT, DEFAULT_USER_PROMPT, SNAPSHOT_SCHEMA
from app.schemas import TemplateIn
from app.services import template_service


def _payload(**kwargs) -> TemplateIn:
    base = dict(
        name="Custom",
        description="d",
        snapshot_type="general",
        system_prompt=BASE_SYSTEM_PROMPT,
        user_prompt=DEFAULT_USER_PROMPT,
        chunk_user_prompt="",
        merge_user_prompt="",
        schema_json=json.dumps(SNAPSHOT_SCHEMA),
        enabled=True,
        is_default=False,
    )
    base.update(kwargs)
    return TemplateIn(**base)


def test_create_template():
    created = template_service.create_template(_payload(name="My Template"))
    assert created.id > 0
    assert created.name == "My Template"
    assert template_service.get_template(created.id) is not None
    template_service.delete_template(created.id)


def test_update_template():
    created = template_service.create_template(_payload(name="Before"))
    updated = template_service.update_template(created.id, _payload(name="After", description="x"))
    assert updated is not None
    assert updated.name == "After"
    assert updated.description == "x"
    template_service.delete_template(created.id)


def test_delete_template():
    created = template_service.create_template(_payload())
    assert template_service.delete_template(created.id) is True
    assert template_service.get_template(created.id) is None
    assert template_service.delete_template(created.id) is False


def test_invalid_schema_rejected():
    with pytest.raises(template_service.TemplateError):
        template_service.create_template(_payload(schema_json="{not json"))
    with pytest.raises(template_service.TemplateError):
        template_service.create_template(_payload(schema_json="[1,2]"))


def test_empty_name_and_prompt_rejected():
    with pytest.raises(template_service.TemplateError):
        template_service.create_template(_payload(name="  "))
    with pytest.raises(template_service.TemplateError):
        template_service.create_template(_payload(system_prompt=""))
    with pytest.raises(template_service.TemplateError):
        template_service.create_template(_payload(user_prompt=""))


def test_invalid_type_rejected():
    with pytest.raises(template_service.TemplateError):
        template_service.create_template(_payload(snapshot_type="banana"))


def test_duplicate_default_for_type():
    from app.services import settings_service

    first = template_service.create_template(_payload(name="D1", is_default=True))
    second = template_service.create_template(_payload(name="D2", is_default=True))
    template_service.set_default(second.id)
    assert settings_service.active_template_id("general") == second.id
    refreshed = template_service.get_template(first.id)
    assert refreshed is not None and refreshed.is_default is False
    template_service.delete_template(first.id)
    template_service.delete_template(second.id)
    template_service.set_default(template_service.get_active_template("general").id)


def test_disabled_template_not_active():
    created = template_service.create_template(_payload(name="Off", is_default=True))
    template_service.set_default(created.id)
    template_service.toggle_enabled(created.id, False)
    active = template_service.get_active_template(created.snapshot_type)
    assert active is None or active.id != created.id
    template_service.toggle_enabled(created.id, True)
    template_service.delete_template(created.id)


def test_get_active_template_returns_enabled_default():
    template = template_service.get_active_template("general")
    assert template is not None
    assert template.enabled is True
    assert template.snapshot_type == "general"


def test_usage_warning():
    template = template_service.get_active_template("article")
    assert template is not None
    warnings = template_service.usage_warnings(template)
    assert any(template.snapshot_type in w for w in warnings)


def test_list_templates_filter():
    items = template_service.list_templates(snapshot_type="news")
    assert items and all(t.snapshot_type == "news" for t in items)
    enabled_only = template_service.list_templates(enabled=True)
    assert all(t.enabled for t in enabled_only)
