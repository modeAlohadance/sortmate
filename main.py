"""Launch SortMate from a source checkout without installing a package."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sortmate.app import main  # noqa: E402

main()
