"""Install a Vosk model into a persistent volume when it is missing."""

import argparse
import pathlib
import shutil
import tempfile
import urllib.request
import zipfile


def _volume_child(volume: pathlib.Path, relative_path: str) -> pathlib.Path:
    """Resolve a path below the model volume and reject paths outside it."""

    candidate = (volume / relative_path).resolve()
    if not candidate.is_relative_to(volume.resolve()):
        raise ValueError(f"Path must stay inside the model volume: {relative_path}")
    return candidate


def _extract_archive(archive: pathlib.Path, destination: pathlib.Path) -> None:
    """Extract a ZIP archive after rejecting entries outside the destination."""

    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as model_zip:
        for member in model_zip.infolist():
            member_path = (destination / member.filename).resolve()
            if not member_path.is_relative_to(destination_root):
                raise RuntimeError(
                    f"Model archive contains an unsafe path: {member.filename}"
                )
        model_zip.extractall(destination)


def install_model(
    *,
    volume: pathlib.Path,
    download_url: str,
    extracted_directory: str,
    target_directory: str = "vosk",
    marker_path: str = "am/final.mdl",
) -> bool:
    """Install the configured model and return whether a download was required."""

    volume.mkdir(parents=True, exist_ok=True)
    source = _volume_child(volume, extracted_directory)
    target = _volume_child(volume, target_directory)
    marker = _volume_child(target, marker_path)

    if marker.is_file():
        print("Vosk model already exists")
        return False

    if source == target:
        raise ValueError("Extracted and target model directories must differ")

    shutil.rmtree(target, ignore_errors=True)
    shutil.rmtree(source, ignore_errors=True)

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as archive_file:
        archive = pathlib.Path(archive_file.name)

    try:
        print("Downloading Vosk model")
        urllib.request.urlretrieve(download_url, archive)
        _extract_archive(archive, volume)

        source_marker = _volume_child(source, marker_path)
        if not source_marker.is_file():
            raise RuntimeError("Downloaded Vosk model does not contain its marker")

        source.rename(target)
        if not marker.is_file():
            raise RuntimeError("Vosk model installation failed")
    finally:
        archive.unlink(missing_ok=True)

    print("Vosk model is ready")
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install a Vosk model into a persistent volume when missing."
    )
    parser.add_argument("--volume", type=pathlib.Path, default=pathlib.Path("/model"))
    parser.add_argument("--download-url", required=True)
    parser.add_argument("--extracted-directory", required=True)
    parser.add_argument("--target-directory", default="vosk")
    parser.add_argument("--marker-path", default="am/final.mdl")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    install_model(
        volume=args.volume,
        download_url=args.download_url,
        extracted_directory=args.extracted_directory,
        target_directory=args.target_directory,
        marker_path=args.marker_path,
    )


if __name__ == "__main__":
    main()
