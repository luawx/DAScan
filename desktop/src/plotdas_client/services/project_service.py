from __future__ import annotations

from pathlib import Path

import yaml

from plotdas_client.models import Project


class ProjectService:
    def __init__(self, config_path: Path):
        self.config_path = config_path

    def list_projects(self) -> list[Project]:
        if not self.config_path.exists():
            return []
        payload = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        return [Project(**item) for item in payload.get("projects", [])]

    def save_projects(self, projects: list[Project]) -> None:
        names = [project.name.strip() for project in projects]
        if any(not name for name in names):
            raise ValueError("项目名称不能为空")
        if len(names) != len(set(names)):
            raise ValueError("项目名称不能重复")
        payload = {
            "projects": [
                {
                    "name": project.name,
                    "server_input": project.server_input,
                    "server_output": project.server_output,
                    "plugin": project.plugin,
                    "description": project.description,
                }
                for project in projects
            ]
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix(".tmp")
        temporary.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
        temporary.replace(self.config_path)

    def upsert(self, project: Project, previous_name: str | None = None) -> list[Project]:
        projects = self.list_projects()
        replaced = False
        updated = []
        for existing in projects:
            if existing.name == (previous_name or project.name):
                updated.append(project)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.append(project)
        self.save_projects(updated)
        return updated

    def delete(self, name: str) -> list[Project]:
        projects = [project for project in self.list_projects() if project.name != name]
        self.save_projects(projects)
        return projects
