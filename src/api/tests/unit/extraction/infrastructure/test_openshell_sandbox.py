"""Unit tests for OpenShell sandbox helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from extraction.infrastructure.openshell.cli import OpenShellCliError
import io
import tarfile

from extraction.infrastructure.openshell.sandbox import (
    _safe_extract_tar,
    create_sandbox,
    delete_sandboxes_by_prefix,
    download_directory_contents,
    download_path,
    sandbox_phase,
    start_forward,
    stop_extraction_job_sandbox,
    upload_directory_contents,
    upload_path,
)


class TestSandboxPhase:
    def test_returns_phase_for_named_sandbox(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
            return_value=MagicMock(
                returncode=0,
                stdout='[{"name":"sb-1","phase":"Ready"}]',
            ),
        ):
            assert sandbox_phase("sb-1") == "Ready"

    def test_returns_none_when_sandbox_missing(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
            return_value=MagicMock(returncode=0, stdout="[]"),
        ):
            assert sandbox_phase("missing") is None


class TestCreateSandbox:
    def test_waits_for_ready_then_terminates_create_process(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = None
        with patch(
            "extraction.infrastructure.openshell.sandbox.popen_openshell",
            return_value=proc,
        ), patch(
            "extraction.infrastructure.openshell.sandbox._wait_for_sandbox_ready",
        ) as wait_ready, patch(
            "extraction.infrastructure.openshell.sandbox._terminate_create_process",
        ) as terminate:
            create_sandbox(
                name="sb-1",
                image="kartograph-agent-runtime:dev",
                provider_name="kartograph-gma",
            )
        wait_ready.assert_called_once_with(name="sb-1", timeout=300.0)
        terminate.assert_called_once_with(proc)

    def test_raises_when_sandbox_enters_error_phase(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.sandbox.popen_openshell",
            return_value=MagicMock(poll=MagicMock(return_value=None)),
        ), patch(
            "extraction.infrastructure.openshell.sandbox.sandbox_phase",
            side_effect=[None, "Error"],
        ), patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
            return_value=MagicMock(returncode=0, stdout="phase=Error", stderr=""),
        ), patch(
            "extraction.infrastructure.openshell.sandbox.time.sleep",
        ):
            with pytest.raises(OpenShellCliError, match="entered Error"):
                create_sandbox(name="sb-1", image="img:dev")


class TestUploadPath:
    def test_passes_dest_as_positional_argument(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
        ) as run:
            upload_path(
                sandbox_name="sb-1",
                local_path="/tmp/work",
                dest="/workspace",
            )
        run.assert_called_once_with(
            [
                "sandbox",
                "upload",
                "--no-git-ignore",
                "sb-1",
                "/tmp/work",
                "/workspace",
            ],
            timeout=600.0,
        )


class TestDownloadPath:
    def test_downloads_into_parent_directory(self, tmp_path) -> None:
        local_file = tmp_path / "mutations" / "result.json"

        def _simulate_openshell_download(args, **kwargs) -> None:
            # OpenShell writes basename(remote path) into the destination directory.
            local_file.parent.mkdir(parents=True, exist_ok=True)
            (local_file.parent / "result.json").write_text("{}", encoding="utf-8")

        with patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
            side_effect=_simulate_openshell_download,
        ) as run_mock:
            download_path(
                sandbox_name="sb-1",
                sandbox_path="/sandbox/mutations/result.json",
                local_path=str(local_file),
            )

        assert local_file.is_file()
        run_mock.assert_called_once_with(
            [
                "sandbox",
                "download",
                "sb-1",
                "/sandbox/mutations/result.json",
                str(local_file.parent),
            ],
            timeout=120.0,
        )

    def test_renames_downloaded_tar_to_requested_local_path(self, tmp_path) -> None:
        local_tar = tmp_path / "nested" / "archive.tar"

        def _simulate_openshell_download(args, **kwargs) -> None:
            local_tar.parent.mkdir(parents=True, exist_ok=True)
            (local_tar.parent / "kartograph-download-sb-1.tar").write_bytes(b"tar-bytes")

        with patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
            side_effect=_simulate_openshell_download,
        ):
            download_path(
                sandbox_name="sb-1",
                sandbox_path="/tmp/kartograph-download-sb-1.tar",
                local_path=str(local_tar),
            )

        assert local_tar.read_bytes() == b"tar-bytes"


class TestDownloadDirectoryContents:
    def test_tars_remote_dir_downloads_and_extracts(self, tmp_path) -> None:
        workdir = tmp_path / "job"
        workdir.mkdir()
        with patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
        ) as run_mock, patch(
            "extraction.infrastructure.openshell.sandbox.download_path",
        ) as download_mock, patch(
            "extraction.infrastructure.openshell.sandbox.tarfile.open",
        ) as tar_open:
            download_directory_contents(
                sandbox_name="sb-1",
                remote_dir="/sandbox/mutations",
                local_dir=workdir,
            )

        tar_cmd = run_mock.call_args_list[0].args[0]
        assert "tar -cf" in tar_cmd[-1]
        assert "/sandbox/mutations" in tar_cmd[-1]
        download_mock.assert_called_once()
        assert download_mock.call_args.kwargs["sandbox_path"].startswith("/tmp/kartograph-download-")
        tar_open.assert_called_once()
        extractall = tar_open.return_value.__enter__.return_value.extractall
        extractall.assert_called_once_with(workdir, filter="data")


class TestSafeExtractTar:
    def test_extracts_members_under_destination(self, tmp_path) -> None:
        destination = tmp_path / "workdir"
        tar_path = tmp_path / "archive.tar"
        with tarfile.open(tar_path, "w") as archive:
            data = tarfile.TarInfo(name="nested/result.json")
            payload = b'{"ok": true}'
            data.size = len(payload)
            archive.addfile(data, fileobj=io.BytesIO(payload))

        with tarfile.open(tar_path, "r") as archive:
            _safe_extract_tar(archive, destination)

        assert (destination / "nested" / "result.json").read_bytes() == payload

    def test_rejects_path_traversal_members(self, tmp_path) -> None:
        destination = tmp_path / "workdir"
        tar_path = tmp_path / "evil.tar"
        with tarfile.open(tar_path, "w") as archive:
            data = tarfile.TarInfo(name="../escape.txt")
            payload = b"pwned"
            data.size = len(payload)
            archive.addfile(data, fileobj=io.BytesIO(payload))

        with tarfile.open(tar_path, "r") as archive:
            with pytest.raises(OpenShellCliError, match="escapes extraction directory"):
                _safe_extract_tar(archive, destination)

        assert not (tmp_path / "escape.txt").exists()


class TestExtractionSandboxCleanup:
    def test_stop_extraction_job_sandbox_deletes_existing_sandbox(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.sandbox.sandbox_exists",
            return_value=True,
        ), patch(
            "extraction.infrastructure.openshell.sandbox.delete_sandbox",
        ) as delete:
            assert stop_extraction_job_sandbox(job_id="job-a") is True
        delete.assert_called_once()

    def test_delete_sandboxes_by_prefix(self) -> None:
        with patch(
            "extraction.infrastructure.openshell.sandbox.list_sandbox_names",
            return_value=[
                "kartograph-extract-job-a",
                "kartograph-gma-session-1",
                "kartograph-extract-job-b",
            ],
        ), patch(
            "extraction.infrastructure.openshell.sandbox.delete_sandbox",
        ) as delete:
            deleted = delete_sandboxes_by_prefix("kartograph-extract-")

        assert deleted == 2
        assert delete.call_count == 2


class TestUploadDirectoryContents:
    def test_uploads_tar_and_extracts_into_dest(self, tmp_path) -> None:
        workdir = tmp_path / "work"
        workdir.mkdir()
        (workdir / "helpers").mkdir()
        (workdir / "helpers" / "sync.py").write_text("print('ok')", encoding="utf-8")

        with patch(
            "extraction.infrastructure.openshell.sandbox.upload_path",
        ) as upload_path_mock, patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
        ) as run_mock:
            upload_directory_contents(
                sandbox_name="sb-1",
                local_dir=str(workdir),
                dest="/sandbox",
            )

        upload_path_mock.assert_called_once()
        uploaded_tar = upload_path_mock.call_args.kwargs["local_path"]
        assert uploaded_tar.endswith(".tar")
        assert upload_path_mock.call_args.kwargs["dest"].startswith("/tmp/kartograph-upload-sb-1")

        run_mock.assert_called_once()
        exec_args = run_mock.call_args.args[0]
        assert exec_args[:4] == ["sandbox", "exec", "--name", "sb-1"]
        extract_cmd = exec_args[-1]
        assert "mkdir -p /sandbox" in extract_cmd
        assert "tar -xf" in extract_cmd
        assert "-C /sandbox" in extract_cmd


class TestUploadGcloudAdc:
    def test_uploads_adc_and_sets_permissions(self, tmp_path) -> None:
        host_gcloud = tmp_path / "gcloud"
        host_gcloud.mkdir()
        adc = host_gcloud / "application_default_credentials.json"
        adc.write_text('{"type":"service_account"}', encoding="utf-8")

        with patch(
            "extraction.infrastructure.openshell.sandbox.run_openshell",
        ) as run, patch(
            "extraction.infrastructure.openshell.sandbox.upload_path",
        ) as upload:
            from extraction.infrastructure.openshell.sandbox import upload_gcloud_adc

            upload_gcloud_adc(
                sandbox_name="sb-1",
                host_gcloud_config_dir=str(host_gcloud),
                container_config_path="/tmp/kartograph-gcloud",
            )

        upload.assert_called_once_with(
            sandbox_name="sb-1",
            local_path=str(adc),
            dest="/tmp/kartograph-gcloud/application_default_credentials.json",
        )
        assert run.call_count == 2
        mkdir_cmd = run.call_args_list[0].args[0][-1]
        assert "mkdir -p /tmp/kartograph-gcloud" in mkdir_cmd
        chmod_cmd = run.call_args_list[1].args[0][-1]
        assert "chmod a+r" in chmod_cmd

    def test_raises_when_adc_missing(self, tmp_path) -> None:
        with pytest.raises(OpenShellCliError, match="Google ADC not found"):
            from extraction.infrastructure.openshell.sandbox import upload_gcloud_adc

            upload_gcloud_adc(
                sandbox_name="sb-1",
                host_gcloud_config_dir=str(tmp_path / "missing"),
                container_config_path="/tmp/kartograph-gcloud",
            )


class TestStartForward:
    def test_raises_when_forwards_state_dir_is_read_only(
        self,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_home = tmp_path / "config"
        forwards_dir = config_home / "openshell" / "forwards"
        forwards_dir.mkdir(parents=True)
        monkeypatch.setenv("KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_XDG_CONFIG_HOME", str(config_home))
        monkeypatch.setattr("os.access", lambda _path, _mode: False)

        with pytest.raises(OpenShellCliError, match="read-only"):
            start_forward(sandbox_name="sb-1", port=18814)

    def test_starts_forward_service_to_agent_runtime_port(
        self,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_home = tmp_path / "config"
        forwards_dir = config_home / "openshell" / "forwards"
        forwards_dir.mkdir(parents=True)
        monkeypatch.setenv("KARTOGRAPH_EXTRACTION_RUNTIME_OPENSHELL_XDG_CONFIG_HOME", str(config_home))

        with patch(
            "extraction.infrastructure.openshell.sandbox.subprocess.Popen",
        ) as popen:
            start_forward(sandbox_name="sb-1", port=18814, target_port=8787)

        popen.assert_called_once()
        command = popen.call_args.args[0]
        assert command == [
            "openshell",
            "forward",
            "service",
            "sb-1",
            "--target-port",
            "8787",
            "--local",
            "18814",
        ]
        assert popen.call_args.kwargs["start_new_session"] is True
