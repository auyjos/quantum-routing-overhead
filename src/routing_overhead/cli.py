"""Command line entry point: validate-config, run, aggregate, plot, control."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from routing_overhead.aggregation import aggregate_run
from routing_overhead.config import ConfigError, load_config
from routing_overhead.controls import control_run
from routing_overhead.experiments import default_run_id, prepare_run_directory, run_grid
from routing_overhead.export import export_run
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
    plot.add_argument(
        "--timing-run",
        action="append",
        default=[],
        metavar="RUN",
        help="repeat run directory contributing compilation times (repeatable)",
    )

    export = subparsers.add_parser(
        "export", help="write a run's summary, raw results, and topologies as JSON"
    )
    export.add_argument("--run", required=True, help="path to a run directory")

    control = subparsers.add_parser(
        "control",
        help="compare each topology against a relabelled copy of the same graph",
    )
    control.add_argument("--run", required=True, help="path to a run directory")
    control.add_argument(
        "--metric",
        default="two_qubit_depth_penalty",
        help="penalty column to compare (default: two_qubit_depth_penalty)",
    )
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
    if args.command == "plot":
        return _plot(args)
    if args.command == "control":
        return _control(args)
    return _export(args)


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
        figures = plot_run(run_dir, timing_runs=[Path(path) for path in args.timing_run])
    except (FileNotFoundError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_ERROR
    for path in figures:
        print(f"wrote {path}")
    print(f"run directory: {run_dir}")
    return EXIT_OK


def _export(args) -> int:
    run_dir = Path(args.run)
    try:
        result = export_run(run_dir)
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return EXIT_ERROR
    print(f"wrote {result['path']}")
    print(f"run directory: {run_dir}")
    return EXIT_OK


def _control(args) -> int:
    run_dir = Path(args.run)
    if not (run_dir / "raw_results.csv").is_file():
        print(f"no raw results in {run_dir}", file=sys.stderr)
        return EXIT_ERROR
    try:
        result = control_run(run_dir, metric=args.metric)
    except (KeyError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return EXIT_ERROR

    print(f"label-permutation control on {result['metric']}")
    if result["controls"]:
        print(f"  named controls: {', '.join(result['controls'])}")
    if result.get("sweeps"):
        members = ", ".join(f"{base} x{n}" for base, n in result["sweeps"].items())
        print(f"  relabelling sweeps: {members}")
    print(f"  configurations compared: {result['configurations']}")
    for row in result["by_level"].itertuples(index=False):
        print(
            f"  {row.base_topology} level={row.optimization_level}: "
            f"{row.label_invariant}/{row.configurations} unchanged, "
            f"{row.systematic} systematic "
            f"(geo-mean {row.geometric_mean_relative_shift:.3f}x, "
            f"max {row.max_relative_shift:.3f}x) -> {row.verdict}"
        )
    if result["clean_levels"]:
        levels = ", ".join(str(level) for level in result["clean_levels"])
        print(f"  levels carrying no labelling bias: {levels}")
    else:
        print("  every level shows a labelling effect")
    systematic = result["systematic"]
    if len(systematic):
        print(f"  systematic shifts ({len(systematic)}), disjoint seed ranges:")
        for row in systematic.nlargest(8, "relative_shift").itertuples(index=False):
            print(
                f"    {row.base_topology} {row.circuit_family} n={row.logical_qubits} "
                f"L{row.optimization_level}: {row.base_median:.3f}x -> "
                f"{row.relabelled_median:.3f}x ({row.relative_shift:.3f}x)"
            )
    distribution = result.get("distribution")
    if distribution is not None and len(distribution):
        print("  relabelling distribution (pooled median penalty per labelling):")
        for row in distribution.itertuples(index=False):
            print(
                f"    {row.base_topology} level={row.optimization_level}: "
                f"identity {row.identity_median:.3f}x ranks {row.identity_rank}/"
                f"{row.sweep_members} (sweep {row.sweep_min:.3f}-{row.sweep_max:.3f}x, "
                f"median {row.sweep_median:.3f}x, spread {row.spread_ratio:.3f}x)"
            )
    ranking = result.get("ranking")
    if ranking is not None and len(ranking):
        print("  ranking robustness across relabellings (level 0 excluded):")
        names = [c[: -len("_cheaper")] for c in ranking.columns if c.endswith("_cheaper")]
        for row in ranking.itertuples(index=False):
            left, right = names
            parts = [
                f"{left} {getattr(row, left + '_cheaper')}",
                f"{right} {getattr(row, right + '_cheaper')}",
            ]
            if row.tied:
                parts.append(f"tied {row.tied}")
            print(
                f"    {row.circuit_family}: " + ", ".join(parts) + f" of {row.comparisons}"
                + ("  (unanimous)" if row.unanimous else "")
            )
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
