from pathlib import Path
from tomllib import load

from arsenal.info import NAME, VERSION


def test_project_metadata_matches_pyproject() -> None:
    """Make sure that the version defined in the code matches the one in pyproject.toml."""

    # Load pyproject.toml and extract project metadata
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as file_handle:
        pyproject = load(file_handle)

    project = pyproject["project"]
    expected_version = tuple(int(part) for part in project["version"].split("."))

    # Assert that the metadata in the code matches the one in pyproject.toml
    assert NAME.casefold() == project["name"].casefold()
    assert VERSION == expected_version
