import json
from dataclasses import asdict, dataclass
from pathlib import Path

SAMPLE_LIBRARY_DIR = Path("data/sample_library")
MANIFEST_PATH = SAMPLE_LIBRARY_DIR / "manifest.json"


@dataclass(frozen=True)
class NaturalSoundSample:
    id: str
    label: str
    category: str
    filename: str
    license: str
    source_url: str | None = None
    attribution: str | None = None


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> list[NaturalSoundSample]:
    if not manifest_path.exists():
        return []

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [NaturalSoundSample(**entry) for entry in data.get("samples", [])]


def list_samples(manifest_path: Path = MANIFEST_PATH) -> list[dict]:
    return [asdict(sample) for sample in load_manifest(manifest_path)]


def get_sample(
    sample_id: str,
    manifest_path: Path = MANIFEST_PATH,
) -> NaturalSoundSample:
    for sample in load_manifest(manifest_path):
        if sample.id == sample_id:
            return sample

    raise ValueError(f"Unknown natural sound sample: {sample_id}")


def resolve_sample_audio_path(
    sample: NaturalSoundSample,
    library_dir: Path = SAMPLE_LIBRARY_DIR,
) -> Path:
    resolved_dir = library_dir.resolve()
    path = (resolved_dir / sample.filename).resolve()

    if path.parent != resolved_dir:
        raise ValueError(f"Invalid sample filename: {sample.filename}")

    if not path.exists():
        raise FileNotFoundError(
            f"Sample audio file not found for '{sample.id}': {sample.filename}. "
            "The manifest entry exists but the licensed audio file has not "
            "been added to the sample library yet -- see "
            "docs/06-factories/natural-sound-sample-library.md."
        )

    return path
