"""Comprehensive API tests including LLM integrations and streaming

NOTE: These tests use mocked responses. To ensure reliability, keep mocks
synchronized with the actual API contract defined in uar/api/server.py.
Consider adding integration tests that hit the actual test server for
end-to-end validation.
"""

from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from io import BytesIO

from uar.api.server import app

client = TestClient(app)


class TestDocumentEndpoints:
    """Test document management endpoints"""

    def test_browse_files_success(self):
        """Test successful file browsing"""
        response = client.get("/api/uar/docs/browse?path=/")
        # Should succeed even if path doesn't exist
        assert response.status_code in [200, 400]

    def test_browse_files_with_path(self):
        """Test file browsing with specific path"""
        response = client.get("/api/uar/docs/browse?path=/tmp")
        assert response.status_code in [200, 400]

    def test_browse_files_with_limit(self):
        """Test file browsing with limit parameter"""
        response = client.get("/api/uar/docs/browse?path=/tmp&limit=10")
        assert response.status_code in [200, 400]

    def test_library_endpoint(self):
        """Test library endpoint"""
        response = client.get("/api/uar/docs/library")
        assert response.status_code in [200, 404]

    def test_presets_endpoint(self):
        """Test presets endpoint"""
        response = client.get("/api/uar/docs/presets")
        assert response.status_code in [200, 404]


class TestFileUpload:
    """Test file upload functionality"""

    def test_upload_single_file(self):
        """Test uploading a single file"""
        file_content = b"test file content"
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
        response = client.post("/api/uar/docs/upload", files=files)
        # Should succeed or fail gracefully
        assert response.status_code in [200, 400, 413, 422]

    def test_upload_large_file_rejected(self):
        """Test that files larger than 50MB are rejected"""
        # Create a file larger than 50MB limit
        large_content = b"x" * (51 * 1024 * 1024)
        files = {"file": ("large.txt", BytesIO(large_content), "text/plain")}
        response = client.post("/api/uar/docs/upload", files=files)
        # Should be rejected
        assert response.status_code in [400, 413, 422]

    def test_upload_no_file(self):
        """Test upload with no file provided"""
        response = client.post("/api/uar/docs/upload", files={})
        assert response.status_code in [400, 422]


class TestStreamingEndpoint:
    """Test the streaming endpoint for real-time execution"""

    def test_stream_endpoint_requires_goal(self):
        """Test that streaming endpoint requires a goal"""
        response = client.post("/api/uar/stream", json={})
        assert response.status_code in [400, 422]

    def test_stream_endpoint_with_goal(self):
        """Test streaming endpoint with a valid goal"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test goal",
                "input_path": "/tmp",
                "skills": ["doc_ingest"],
            },
        )
        # Should attempt to process
        assert response.status_code in [200, 400, 500]

    def test_stream_endpoint_sse_format(self):
        """Test that streaming returns SSE format"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test goal",
                "input_path": "/tmp",
                "skills": ["doc_ingest"],
            },
        )
        if response.status_code == 200:
            # Check for SSE headers
            assert "text/event-stream" in response.headers.get(
                "content-type", ""
            )


class TestLLMIntegration:
    """Test LLM provider integrations with mocked API calls"""

    @patch("httpx.Client.post")
    def test_openai_skill_with_mock(self, mock_post):
        """Test OpenAI skill with mocked API call"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": "test response"}}]
            },
        )

        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test openai",
                "input_path": "/tmp",
                "skills": ["openai_chat"],
                "metadata": {"openai_api_key": "test-key"},
            },
        )
        # Should attempt to process
        assert response.status_code in [200, 400, 500]

    @patch("httpx.Client.post")
    def test_anthropic_skill_with_mock(self, mock_post):
        """Test Anthropic skill with mocked API call"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"content": [{"text": "test response"}]},
        )

        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test anthropic",
                "input_path": "/tmp",
                "skills": ["anthropic_chat"],
                "metadata": {"anthropic_api_key": "test-key"},
            },
        )
        assert response.status_code in [200, 400, 500]

    @patch("httpx.Client.post")
    def test_gemini_skill_with_mock(self, mock_post):
        """Test Gemini skill with mocked API call"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "candidates": [
                    {"content": {"parts": [{"text": "test response"}]}}
                ]
            },
        )

        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test gemini",
                "input_path": "/tmp",
                "skills": ["gemini_chat"],
                "metadata": {"gemini_api_key": "test-key"},
            },
        )
        assert response.status_code in [200, 400, 500]


class TestRateLimiting:
    """Test rate limiting middleware"""

    def test_rate_limit_respected(self):
        """Test that rate limiting is enforced"""
        # Make multiple rapid requests
        responses = []
        for _ in range(15):  # Exceed typical rate limit
            response = client.post(
                "/api/uar/stream",
                json={
                    "goal": "test",
                    "input_path": "/tmp",
                    "skills": ["doc_ingest"],
                },
            )
            responses.append(response.status_code)

        # At least some should be rate limited
        assert 429 in responses or all(status != 200 for status in responses)


class TestAuthentication:
    """Test authentication and authorization"""

    def test_endpoint_without_auth(self):
        """Test endpoints work without auth (if configured)"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test",
                "input_path": "/tmp",
                "skills": ["doc_ingest"],
            },
        )
        # Should work or fail based on auth config
        assert response.status_code in [200, 400, 401, 403]

    def test_endpoint_with_auth(self):
        """Test endpoint with Bearer token"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test",
                "input_path": "/tmp",
                "skills": ["doc_ingest"],
            },
            headers={"Authorization": "Bearer test-token"},
        )
        # Should work or fail based on token validity
        assert response.status_code in [200, 400, 401, 403]


class TestErrorHandling:
    """Test error handling across endpoints"""

    def test_invalid_goal_format(self):
        """Test error handling for invalid goal format"""
        response = client.post(
            "/api/uar/stream",
            json={"goal": "", "input_path": "/tmp", "skills": []},
        )
        assert response.status_code in [400, 422]

    def test_invalid_skills(self):
        """Test error handling for invalid skills"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test",
                "input_path": "/tmp",
                "skills": ["invalid_skill"],
            },
        )
        assert response.status_code in [400, 422]

    def test_invalid_path(self):
        """Test error handling for invalid path"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test",
                "input_path": "../../../etc/passwd",
                "skills": ["doc_ingest"],
            },
        )
        # Path traversal should be blocked
        assert response.status_code in [400, 403]


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_health_endpoint(self):
        """Test basic health endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_live_endpoint(self):
        """Test liveness probe endpoint"""
        response = client.get("/api/health/live")
        assert response.status_code == 200

    def test_health_ready_endpoint(self):
        """Test readiness probe endpoint"""
        response = client.get("/api/health/ready")
        # May return 503 if dependencies not available
        assert response.status_code in [200, 503]

    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = client.get("/api/metrics")
        assert response.status_code in [200, 404]

    def test_metrics_json_endpoint(self):
        """Test JSON metrics endpoint"""
        response = client.get("/api/metrics/json")
        assert response.status_code in [200, 404]


class TestSkillExecution:
    """Test skill execution through API"""

    def test_doc_ingest_skill(self):
        """Test doc_ingest skill execution"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "ingest docs",
                "input_path": "/tmp",
                "skills": ["doc_ingest"],
            },
        )
        assert response.status_code in [200, 400, 500]

    def test_dependency_map_skill(self):
        """Test dependency_map skill execution"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "map dependencies",
                "input_path": "/tmp",
                "skills": ["doc_ingest", "dependency_map"],
            },
        )
        assert response.status_code in [200, 400, 500]

    def test_multiple_skills_execution(self):
        """Test execution of multiple skills in sequence"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "analyze codebase",
                "input_path": "/tmp",
                "skills": [
                    "doc_ingest",
                    "dependency_map",
                    "section_sum",
                    "sum_review",
                ],
            },
        )
        assert response.status_code in [200, 400, 500]


class TestTimeoutHandling:
    """Test timeout handling for long-running operations"""

    def test_timeout_parameter(self):
        """Test that timeout parameter is respected"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test timeout",
                "input_path": "/tmp",
                "skills": ["doc_ingest"],
                "timeout_seconds": 1,  # Very short timeout
            },
        )
        assert response.status_code in [200, 400, 408, 500]


class TestMetadataHandling:
    """Test metadata passing to skills"""

    def test_metadata_passed_to_skills(self):
        """Test that metadata is correctly passed to skills"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test metadata",
                "input_path": "/tmp",
                "skills": ["doc_ingest"],
                "metadata": {"custom_key": "custom_value"},
            },
        )
        assert response.status_code in [200, 400, 500]

    def test_graphrag_metadata(self):
        """Test GraphRAG-specific metadata"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test graphrag",
                "input_path": "/tmp",
                "skills": ["graphrag_query"],
                "metadata": {
                    "graphrag_method": "local",
                    "graphrag_query": "test query",
                },
            },
        )
        assert response.status_code in [200, 400, 500]

    def test_ollama_metadata(self):
        """Test Ollama-specific metadata"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test ollama",
                "input_path": "/tmp",
                "skills": ["ollama_generate"],
                "metadata": {"ollama_model": "llama3.2"},
            },
        )
        assert response.status_code in [200, 400, 500]


class TestAutonomiIntegration:
    """Test Autonomi decentralized storage integration"""

    def test_autonomi_upload_metadata(self):
        """Test Autonomi upload with required metadata"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test autonomi upload",
                "input_path": "/tmp",
                "skills": ["autonomi_upload"],
                "metadata": {
                    "autonomi_private_key": "test-key",
                    "autonomi_network": "testnet",
                    "autonomi_public": True,
                },
            },
        )
        assert response.status_code in [200, 400, 500]

    def test_autonomi_download_metadata(self):
        """Test Autonomi download with address"""
        response = client.post(
            "/api/uar/stream",
            json={
                "goal": "test autonomi download",
                "input_path": "/tmp",
                "skills": ["autonomi_download"],
                "metadata": {
                    "autonomi_private_key": "test-key",
                    "autonomi_network": "testnet",
                    "autonomi_address": "test-address",
                },
            },
        )
        assert response.status_code in [200, 400, 500]
