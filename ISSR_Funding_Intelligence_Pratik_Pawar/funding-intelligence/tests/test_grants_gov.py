"""Tests for the Grants.gov API client."""

from unittest.mock import Mock, patch

import pytest
import requests

from foa_pipeline.ingestion.grants_gov import GrantsGovClient


@pytest.fixture
def client(test_config):
    return GrantsGovClient(test_config)


class TestGrantsGovClient:
    @patch("requests.Session.post")
    def test_post_success(self, mock_post, client):
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        # Execute
        result = client._post("test_endpoint", {"data": 123})

        # Assert
        assert result == {"success": True}
        mock_post.assert_called_once()

    @patch("time.sleep", return_value=None)  # avoid actually sleeping
    @patch("requests.Session.post")
    def test_post_retry_on_server_error(self, mock_post, mock_sleep, client):
        # Setup mock to fail twice with 500, then succeed
        error_response = Mock()
        error_response.status_code = 500

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"success": True}

        mock_post.side_effect = [error_response, error_response, success_response]

        # Execute
        result = client._post("test_endpoint", {"data": 123})

        # Assert
        assert result == {"success": True}
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.post")
    def test_post_retry_on_exception(self, mock_post, mock_sleep, client):
        # Setup mock to raise exception twice, then succeed
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"success": True}

        mock_post.side_effect = [
            requests.RequestException("Timeout"),
            requests.RequestException("Connection error"),
            success_response,
        ]

        # Execute
        result = client._post("test_endpoint", {"data": 123})

        # Assert
        assert result == {"success": True}
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.post")
    def test_post_max_retries_exhausted(self, mock_post, mock_sleep, client):
        # Setup mock to always fail
        error_response = Mock()
        error_response.status_code = 500
        mock_post.return_value = error_response

        # Execute & Assert
        with pytest.raises(RuntimeError, match="request failed after 5 attempts"):
            client._post("test_endpoint", {"data": 123})

        assert mock_post.call_count == 5
        assert mock_sleep.call_count == 5


class TestGrantsGovClientAttachments:
    @patch("requests.Session.get")
    def test_download_attachment_success(self, mock_get, client, tmp_path):
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_get.return_value = mock_response

        output_file = tmp_path / "test.pdf"

        # Execute
        result = client.download_attachment("123", output_file)

        # Assert
        assert result is True
        assert output_file.read_bytes() == b"chunk1chunk2"
        mock_get.assert_called_once()

    @patch("requests.Session.get")
    def test_download_attachment_failure(self, mock_get, client, tmp_path):
        # Setup mock to raise error
        mock_get.side_effect = requests.RequestException("Network error")

        output_file = tmp_path / "test.pdf"

        # Execute
        result = client.download_attachment("123", output_file)

        # Assert
        assert result is False
        assert not output_file.exists()
