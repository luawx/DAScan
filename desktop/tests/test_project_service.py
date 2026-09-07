from plotdas_client.models import Project
from plotdas_client.services import ProjectService


def test_project_crud_is_persisted(tmp_path):
    service = ProjectService(tmp_path / "config" / "projects.yaml")
    first = Project("alpha", "/input/a", "/output/a", "plugin_a", "A")
    second = Project("beta", "/input/b", "/output/b", "plugin_b", "B")

    assert service.upsert(first) == [first]
    assert service.upsert(second) == [first, second]
    renamed = Project("beta-new", "/input/b", "/output/new", "plugin_b", "renamed")
    assert service.upsert(renamed, "beta") == [first, renamed]
    assert service.delete("alpha") == [renamed]
    assert service.list_projects() == [renamed]


def test_duplicate_project_name_is_rejected(tmp_path):
    service = ProjectService(tmp_path / "projects.yaml")
    project = Project("same", "/a", "/b", "plugin")

    try:
        service.save_projects([project, project])
    except ValueError as exc:
        assert "不能重复" in str(exc)
    else:
        raise AssertionError("duplicate names should fail")
