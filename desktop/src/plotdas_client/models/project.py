from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Project:
    name: str
    server_input: str
    server_output: str
    plugin: str
    description: str = ""
