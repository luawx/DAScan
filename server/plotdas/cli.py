from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import click

from .config import load_config
from .exceptions import PlotDASError
from .jobs.manager import JobManager
from .models import FilterConfig, PlotRequest, ScaleConfig
from .registry import get_plugin
from .timeutil import parse_datetime


def common_plot_options(function: Callable) -> Callable:
    options = [
        click.option("--start", required=True, help="Start time, inclusive"),
        click.option("--end", required=True, help="End time, exclusive"),
        click.option("--channel-start", required=True, type=int),
        click.option("--channel-end", required=True, type=int),
        click.option("--project", default=None),
        click.option("--input", "input_root", type=click.Path(path_type=Path), default=None),
        click.option("--output-root", type=click.Path(path_type=Path), default=None),
        click.option("--filter", "filter_type", type=click.Choice(["none", "bandpass", "lowpass", "highpass"]), default=None),
        click.option("--lowcut", type=float, default=None),
        click.option("--highcut", type=float, default=None),
        click.option("--filter-order", type=int, default=None),
        click.option("--dpi", type=int, default=None),
        click.option("--scale-mode", type=click.Choice(["percentile", "absolute", "std"]), default=None),
        click.option("--percentile", type=float, default=None),
        click.option("--absolute-scale", type=float, default=None),
        click.option("--std-factor", type=float, default=None),
        click.option("--overwrite", is_flag=True),
    ]
    for option in reversed(options):
        function = option(function)
    return function


def build_request(config: dict[str, Any], values: dict[str, Any]) -> PlotRequest:
    filter_defaults = config["filter"]
    scale_defaults = config["scale"]
    plot_defaults = config["plot"]
    reader_defaults = config["reader"]
    timezone = config["timezone"]
    return PlotRequest(
        project=values.get("project") or config["project"],
        input_root=values.get("input_root") or Path(config["input_root"]),
        output_root=values.get("output_root") or Path(config["output_root"]),
        start_time=parse_datetime(values["start"], timezone),
        end_time=parse_datetime(values["end"], timezone),
        channel_start=values["channel_start"],
        channel_end=values["channel_end"],
        filter=FilterConfig(
            type=values.get("filter_type") or filter_defaults.get("type", "none"),
            lowcut=values.get("lowcut") if values.get("lowcut") is not None else filter_defaults.get("lowcut"),
            highcut=values.get("highcut") if values.get("highcut") is not None else filter_defaults.get("highcut"),
            order=values.get("filter_order") or filter_defaults.get("order", 4),
        ),
        scale=ScaleConfig(
            mode=values.get("scale_mode") or scale_defaults.get("mode", "percentile"),
            percentile=values.get("percentile") or scale_defaults.get("percentile", 99.0),
            absolute=values.get("absolute_scale") if values.get("absolute_scale") is not None else scale_defaults.get("absolute"),
            std_factor=values.get("std_factor") or scale_defaults.get("std_factor", 3.0),
        ),
        dpi=values.get("dpi") or plot_defaults.get("dpi", 200),
        image_format=plot_defaults.get("format", "png"),
        figsize=tuple(plot_defaults.get("figsize", [14.0, 8.0])),
        max_time_pixels=plot_defaults.get("max_time_pixels", 6000),
        timezone=timezone,
        overwrite=bool(values.get("overwrite")),
        output_path=values.get("output_path"),
        gap_tolerance_samples=reader_defaults.get("gap_tolerance_samples", 0.5),
        channel_block_size=reader_defaults.get("channel_block_size", 64),
        memory_limit_mb=reader_defaults.get("memory_limit_mb", 8192),
        temp_root=Path(reader_defaults.get("temp_root", "/tmp")),
    )


@click.group()
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None) -> None:
    """Inspect and batch-plot DAS HDF5 data."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config_path)


@cli.command("inspect")
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
@click.option("--project", default=None)
@click.option("--limit", default=10, show_default=True, type=click.IntRange(1, 1000))
@click.pass_context
def inspect_command(ctx: click.Context, path: Path | None, project: str | None, limit: int) -> None:
    """Inspect one HDF5 file or a directory of files without reading full arrays."""
    config = ctx.obj["config"]
    selected = path or Path(config["input_root"])
    plugin = get_plugin(project or config["project"])
    paths = [selected] if selected.is_file() else sorted(selected.rglob("*.h5"))[:limit]
    results = []
    for item in paths:
        try:
            info = plugin.inspect_file(item)
            results.append({**vars(info), "path": str(info.path), "start_time": info.start_time.isoformat(), "end_time": info.end_time.isoformat()})
        except Exception as exc:
            results.append({"path": str(item), "error": f"{type(exc).__name__}: {exc}"})
    click.echo(json.dumps(results, ensure_ascii=False, indent=2, default=str))


@cli.command("plot")
@common_plot_options
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None, help="Explicit image path; otherwise use organized output root")
@click.pass_context
def plot_command(ctx: click.Context, **values: Any) -> None:
    """Render one DAS time/channel window."""
    request = build_request(ctx.obj["config"], values)
    result = get_plugin(request.project).plot(request)
    click.echo(json.dumps({"image": str(result.image_path), "metadata": str(result.metadata_path)}, ensure_ascii=False))


@cli.group("job")
def job_group() -> None:
    """Create and manage batch plotting jobs."""


@job_group.command("create")
@common_plot_options
@click.option("--window-length", required=True, type=click.FloatRange(min=0, min_open=True), help="Window length in seconds")
@click.pass_context
def job_create(ctx: click.Context, window_length: float, **values: Any) -> None:
    config = ctx.obj["config"]
    request = build_request(config, values)
    job = JobManager(Path(config["jobs_root"])).create_job(request, window_length)
    click.echo(json.dumps(job, ensure_ascii=False, indent=2))


@job_group.command("create-all")
@click.option("--channel-start", required=True, type=int)
@click.option("--channel-end", required=True, type=int)
@click.option("--project", default=None)
@click.option("--input", "input_root", type=click.Path(path_type=Path), default=None)
@click.option("--output-root", type=click.Path(path_type=Path), default=None)
@click.option("--filter", "filter_type", type=click.Choice(["none", "bandpass", "lowpass", "highpass"]), default=None)
@click.option("--lowcut", type=float, default=None)
@click.option("--highcut", type=float, default=None)
@click.option("--filter-order", type=int, default=None)
@click.option("--dpi", type=int, default=None)
@click.option("--window-length", required=True, type=click.FloatRange(min=0, min_open=True))
@click.option("--workers", default=8, show_default=True, type=click.IntRange(1, 32))
@click.option("--overwrite", is_flag=True)
@click.pass_context
def job_create_all(ctx: click.Context, window_length: float, workers: int, **values: Any) -> None:
    """Discover every readable continuous interval and create one manifest job."""
    from .jobs.discovery import discover_all_windows

    config = ctx.obj["config"]
    input_root = values.get("input_root") or Path(config["input_root"])
    windows, discovery = discover_all_windows(input_root, values["channel_end"], window_length, workers)
    if not windows:
        raise PlotDASError("No eligible data windows discovered")
    values.update({"start": windows[0][0].isoformat(), "end": windows[-1][1].isoformat(), "input_root": input_root})
    request = build_request(config, values)
    job = JobManager(Path(config["jobs_root"])).create_job_from_windows(
        request,
        windows,
        window_length,
        continue_on_error=True,
        discovery=discovery,
    )
    click.echo(json.dumps({"job": job, "discovery": discovery}, ensure_ascii=False, indent=2))


@job_group.command("start")
@click.argument("job_id")
@click.pass_context
def job_start(ctx: click.Context, job_id: str) -> None:
    job = JobManager(Path(ctx.obj["config"]["jobs_root"])).start_job(job_id)
    click.echo(json.dumps(job, ensure_ascii=False, indent=2))


@job_group.command("status")
@click.argument("job_id")
@click.pass_context
def job_status(ctx: click.Context, job_id: str) -> None:
    click.echo(json.dumps(JobManager(Path(ctx.obj["config"]["jobs_root"])).get_job(job_id), ensure_ascii=False, indent=2))


@job_group.command("list")
@click.pass_context
def job_list(ctx: click.Context) -> None:
    click.echo(json.dumps(JobManager(Path(ctx.obj["config"]["jobs_root"])).list_jobs(), ensure_ascii=False, indent=2))


@job_group.command("cancel")
@click.argument("job_id")
@click.pass_context
def job_cancel(ctx: click.Context, job_id: str) -> None:
    click.echo(json.dumps(JobManager(Path(ctx.obj["config"]["jobs_root"])).cancel_job(job_id), ensure_ascii=False, indent=2))


def main() -> None:
    try:
        cli(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        raise SystemExit(exc.exit_code)
    except PlotDASError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
