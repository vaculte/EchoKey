"""Tests for the Vosk model installation utility."""

import pathlib
import shutil
import zipfile
from unittest.mock import Mock

import pytest

from app.scripts import install_vosk_model


def test_existing_model_skips_download(tmp_path, monkeypatch):
    marker = tmp_path / "vosk" / "am" / "final.mdl"
    marker.parent.mkdir(parents=True)
    marker.touch()
    download = Mock()
    monkeypatch.setattr(install_vosk_model.urllib.request, "urlretrieve", download)

    installed = install_vosk_model.install_model(
        volume=tmp_path,
        download_url="https://example.test/model.zip",
        extracted_directory="downloaded-model",
    )

    assert installed is False
    download.assert_not_called()


def test_downloaded_model_is_installed(tmp_path, monkeypatch):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as model_zip:
        model_zip.writestr("downloaded-model/am/final.mdl", "model")

    def copy_archive(_url: str, destination: pathlib.Path):
        shutil.copyfile(archive, destination)

    monkeypatch.setattr(
        install_vosk_model.urllib.request,
        "urlretrieve",
        copy_archive,
    )
    volume = tmp_path / "volume"

    installed = install_vosk_model.install_model(
        volume=volume,
        download_url="https://example.test/model.zip",
        extracted_directory="downloaded-model",
    )

    assert installed is True
    assert (volume / "vosk" / "am" / "final.mdl").read_text() == "model"
    assert not (volume / "downloaded-model").exists()


def test_download_without_marker_fails(tmp_path, monkeypatch):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as model_zip:
        model_zip.writestr("downloaded-model/README", "not a model")

    def copy_archive(_url: str, destination: pathlib.Path):
        shutil.copyfile(archive, destination)

    monkeypatch.setattr(
        install_vosk_model.urllib.request,
        "urlretrieve",
        copy_archive,
    )

    with pytest.raises(RuntimeError, match="does not contain its marker"):
        install_vosk_model.install_model(
            volume=tmp_path / "volume",
            download_url="https://example.test/model.zip",
            extracted_directory="downloaded-model",
        )
