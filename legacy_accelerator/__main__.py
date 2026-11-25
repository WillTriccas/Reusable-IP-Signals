import argparse
import json
from pathlib import Path

from .analysis import analyze, render_report


def main():
    parser = argparse.ArgumentParser(description="Assess public or synthetic legacy Python code")
    parser.add_argument("source", type=Path, help="Python file or directory to assess")
    parser.add_argument("--output", type=Path, required=True, help="Directory for JSON and Markdown reports")
    args = parser.parse_args()
    try:
        result = analyze(args.source)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "assessment.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        (args.output / "report.md").write_text(render_report(result), encoding="utf-8")
    except (OSError, ValueError, SyntaxError) as error:
        parser.exit(1, f"Assessment failed: {error}\n")
    print(f"Assessment written to {args.output}")


if __name__ == "__main__":
    main()
