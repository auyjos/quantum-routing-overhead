"""Command line entry point: validate-config, run, aggregate, plot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from routing_overhead.aggregation import aggregate_run
from routing_overhead.config import ConfigError, load_config
from routing_overhead.experiments import default_run_id, prepare_run_directory, run_grid
from routing_overhead.plotting import plot_run

DEFAULT_ARTIFACTS = Path("artifacts") / "runs"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="routing-overhead", description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    validate = subparsers.add_parser("validate-config", help="validate an experiment config")
    validate.add_argument("config", help="path to a YAML configuration file")

    run = subparsers.add_parser("run", help="execute an experiment grid")
    run.add_argument("--config", required=True, help="path to a YAML configuration file")
    run.add_argument("--artifacts", default=str(DEFAULT_ARTIFACTS), help="run directory root")
    run.add_argument("--run-id", default=None, help="run identifier (default: timestamped)")
    run.add_argument("--resume", action="store_true", help="continue an interrupted run")

    aggregate = subparsers.add_parser("aggregate", help="join baselines and summarize a run")
    aggregate.add_argument("--run", required=True, help="path to a run directory")

    plot = subparsers.add_parser("plot", help="draw figures from a run's summary data")
    plot.add_argument("--run", required=True, help="path to a run directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    if args.command == "validate-config":
        return _validate_config(args)
    if args.command == "run":
        return _run(args)
    if args.command == "aggregate":
        return _aggregate(args)
    return _plot(args)


def _validate_config(args) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"invalid configuration: {error}", file=sys.stderr)
        return EXIT_USAGE
    print(f"{args.config} is valid: {config.size()} planned transpilations")
    print(f"  basis: {','.join(config.basis_gates)} (hash {config.basis_hash[:12]})")
    return EXIT_OK


def _run(args) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"invalid configuration: {error}", file=sys.stderr)
        return EXIT_USAGE

    run_id = args.run_id or default_run_id(args.config)
    try:
        run_dir = prepare_run_directory(config, args.artifacts, run_id, resume=args.resume)
    except (FileExistsError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_ERROR

    counts = run_grid(config, run_dir, on_result=_print_progress)
    print(
        f"planned={counts['planned']} executed={counts['executed']} "
        f"skipped={counts['skipped']} failed={counts['failed']}"
    )
    print(f"run directory: {run_dir}")
    return EXIT_OK


def _aggregate(args) -> int:
    run_dir = Path(args.run)
    if not (run_dir / "raw_results.csv").is_file():
        print(f"no raw results in {run_dir}", file=sys.stderr)
        return EXIT_ERROR
    result = aggregate_run(run_dir)
    for warning in result["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"aggregated {result['rows']} rows into {result['summary_rows']} summary rows")
    print(f"run directory: {run_dir}")
    return EXIT_OK


def _plot(args) -> int:
    run_dir = Path(args.run)
    try:
        figures = plot_run(run_dir)
    except (FileNotFoundError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_ERROR
    for path in figures:
        print(f"wrote {path}")
    print(f"run directory: {run_dir}")
    return EXIT_OK


def _print_progress(index: int, total: int, row: dict) -> None:
    status = "ok" if row["success"] else f"FAILED ({row['exception_type']})"
    print(
        f"[{index}/{total}] {row['circuit_family']} n={row['logical_qubits']} "
        f"{row['topology']} level={row['optimization_level']} seed={row['transpiler_seed']} "
        f"{status}",
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
