from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..exceptions import OutputExistsError
from ..models import DASData, FileInfo, PlotRequest, PlotResult


class DASPlotPlugin(ABC):
    name: str
    version: str

    @abstractmethod
    def inspect_file(self, path: Path) -> FileInfo:
        raise NotImplementedError

    @abstractmethod
    def read(self, request: PlotRequest) -> DASData:
        raise NotImplementedError

    @abstractmethod
    def process(self, data: DASData, request: PlotRequest) -> DASData:
        raise NotImplementedError

    @abstractmethod
    def render(self, data: DASData, request: PlotRequest) -> PlotResult:
        raise NotImplementedError

    def plot(self, request: PlotRequest) -> PlotResult:
        request.validate()
        data = None
        try:
            data = self.read(request)
            processed = self.process(data, request)
            return self.render(processed, request)
        except OutputExistsError:
            raise
        except Exception as exc:
            from ..output import write_failure_metadata

            try:
                write_failure_metadata(request, self.name, self.version, exc)
            except Exception as metadata_error:
                exc.add_note(f"Additionally failed to write failure metadata: {metadata_error}")
            raise
        finally:
            if data is not None:
                for temporary in data.temporary_files:
                    try:
                        Path(temporary).unlink(missing_ok=True)
                    except OSError:
                        pass
