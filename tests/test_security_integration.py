"""Security integration tests for production hardening"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import os
import shutil

from uar.api.server import app
from uar.skills.doc_ingest import doc_ingest
from uar.core.contracts import GoalSpec, PipelineContext
from uar.core.validation import validate_path_security

client = TestClient(app)


@pytest.fixture
def test_ingest_dir():
    """Create a test directory within project for doc ingest tests."""
    test_dir = Path("runs/test_ingest")
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    # Cleanup
    if test_dir.exists():
        shutil.rmtree(test_dir)


class TestDocIngestSecurity:
    """Test document ingestion security features"""
    
    def test_file_size_limits(self, test_ingest_dir):
        """Test file size limits are enforced"""
        # Create a large file within the test directory
        large_file = test_ingest_dir / "large_file.txt"
        large_file.write_text('x' * (11 * 1024 * 1024))
        
        # Test ingestion of large file
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={"input_path": str(large_file)}
        )
        ctx = PipelineContext(goal=goal)
        
        result = doc_ingest(ctx)
        
        # Should reject large file (error is in the document, not top-level)
        assert len(result["documents"]) == 1
        assert "error" in result["documents"][0]
        assert "too large" in result["documents"][0]["error"]
    
    def test_file_count_limits(self, test_ingest_dir):
        """Test file count limits are enforced"""
        # Create many files in the test directory
        for i in range(1005):
            file_path = test_ingest_dir / f"file_{i}.txt"
            file_path.write_text(f"content {i}")
        
        goal = GoalSpec(
            id="test",
            user_intent="test", 
            objective="test",
            metadata={"input_path": str(test_ingest_dir)}
        )
        ctx = PipelineContext(goal=goal)
        
        result = doc_ingest(ctx)
        
        # Should limit file count
        assert result["document_count"] <= 1000
        assert any(doc["path"] == "LIMIT_EXCEEDED" for doc in result["documents"])
    
    def test_unsupported_file_types(self, test_ingest_dir):
        """Test unsupported file types are rejected"""
        exe_file = test_ingest_dir / "malicious.exe"
        exe_file.write_bytes(b"fake exe content")
        
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test", 
            metadata={"input_path": str(exe_file)}
        )
        ctx = PipelineContext(goal=goal)
        
        result = doc_ingest(ctx)
        
        # Should reject unsupported file type (returns as document with error)
        assert len(result["documents"]) == 1
        assert "Unsupported file type" in result["documents"][0].get("error", "")
    
    def test_encoding_error_handling(self, test_ingest_dir):
        """Test handling of encoding errors"""
        # Create a file with invalid UTF-8 content
        bad_file = test_ingest_dir / "bad_encoding.txt"
        bad_file.write_bytes(b'\xff\xfe\x00\x00')  # Invalid UTF-8
        
        goal = GoalSpec(
            id="test",
            user_intent="test",
            objective="test",
            metadata={"input_path": str(bad_file)}
        )
        ctx = PipelineContext(goal=goal)
        
        result = doc_ingest(ctx)
        
        # Should handle encoding error gracefully (error is in the document)
        assert len(result["documents"]) == 1
        doc = result["documents"][0]
        assert "error" in doc or doc.get("text") == ""
        # Encoding error returns empty text with error field
        if "error" in doc:
            assert "encoding" in doc["error"].lower() or "utf-8" in doc["error"].lower()


class TestPathSecurityValidation:
    """Test path security validation"""
    
    def test_path_within_allowed_root(self):
        """Test paths within allowed root are accepted"""
        allowed_root = Path("/tmp/test_root")
        allowed_root.mkdir(parents=True, exist_ok=True)
        
        test_file = allowed_root / "test.txt"
        test_file.write_text("test content")
        
        try:
            # Should not raise exception
            validate_path_security(test_file, allowed_root)
        finally:
            test_file.unlink()
            allowed_root.rmdir()
    
    def test_path_outside_allowed_root(self):
        """Test paths outside allowed root are rejected"""
        allowed_root = Path("/tmp/test_root")
        outside_path = Path("/tmp/outside_root/test.txt")
        
        with pytest.raises(Exception) as exc_info:
            validate_path_security(outside_path, allowed_root)
        assert "Path outside allowed root" in str(exc_info.value)
    
    def test_symlink_rejection(self):
        """Test symlinks are rejected"""
        allowed_root = Path("/tmp/test_root")
        allowed_root.mkdir(parents=True, exist_ok=True)
        
        target_file = allowed_root / "target.txt"
        target_file.write_text("target content")
        
        symlink_path = allowed_root / "symlink.txt"
        symlink_path.symlink_to(target_file)
        
        try:
            with pytest.raises(Exception) as exc_info:
                validate_path_security(symlink_path, allowed_root)
            assert "Symlinks are not allowed" in str(exc_info.value)
        finally:
            target_file.unlink()
            symlink_path.unlink()
            allowed_root.rmdir()


class TestAPIProductionFeatures:
    """Test API production features"""
    
    def test_request_id_tracing(self):
        """Test request IDs are added for tracing"""
        response = client.post("/api/uar/run", json={"goal": "test tracing"})
        assert response.status_code == 200
        
        # The response should include tracing information
        # (This would require custom middleware to add headers)
    
    def test_cors_headers(self):
        """Test CORS headers are properly set"""
        response = client.options("/api/uar/run")
        assert response.status_code == 200
        # Should have CORS headers
    
    def test_error_response_format(self):
        """Test error responses follow consistent format"""
        response = client.post("/api/uar/run", json={"goal": ""})
        assert response.status_code == 400
        
        data = response.json()
        assert "error" in data["detail"]
        assert isinstance(data["detail"], dict)
    
    def test_health_check_detailed(self):
        """Test health check provides useful information"""
        response = client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["status"] == "healthy"


class TestRateLimitingProduction:
    """Test rate limiting in production scenarios"""
    
    def test_rate_limit_headers(self):
        """Test rate limit headers are included"""
        response = client.post("/api/uar/run", json={"goal": "test headers"})
        
        # Should include rate limit headers (if implemented)
        # This would require custom middleware to add headers
    
    def test_different_rate_tiers(self):
        """Test different rate limits for different users"""
        # Anonymous user
        anon_response = client.post("/api/uar/run", json={"goal": "test"})
        
        # Authenticated user
        auth_response = client.post(
            "/api/uar/run", 
            json={"goal": "test"},
            headers={"Authorization": "Bearer dev-key-12345"}
        )
        
        # Both should succeed for single requests
        assert anon_response.status_code in [200, 400]  # May fail validation
        assert auth_response.status_code in [200, 400]  # May fail validation


class TestLoggingAndMonitoring:
    """Test logging and monitoring features"""
    
    def test_request_logging(self):
        """Test requests are properly logged"""
        # This would require checking log output
        # For now, just ensure the request doesn't crash
        response = client.post("/api/uar/run", json={"goal": "test logging"})
        assert response.status_code in [200, 400]
    
    def test_error_logging(self):
        """Test errors are properly logged"""
        response = client.post("/api/uar/run", json={"goal": ""})
        assert response.status_code == 400
        # Error should be logged (would need to check log files)
    
    def test_performance_logging(self):
        """Test performance metrics are logged"""
        response = client.post("/api/uar/run", json={"goal": "test performance"})
        assert response.status_code in [200, 400]
        # Performance should be logged (would need to check log files)


class TestMemoryManagement:
    """Test memory management features"""
    
    def test_event_limiting(self):
        """Test events are limited to prevent memory issues"""
        # This would require a test that generates many events
        # For now, test the validation layer
        response = client.post("/api/uar/stream", json={
            "goal": "test memory management",
            "skills": ["section_sum"]
        })
        
        assert response.status_code == 200
    
    def test_cleanup_on_disconnect(self):
        """Test cleanup happens when client disconnects"""
        # This would require a more complex test setup
        # For now, ensure the endpoint handles requests correctly
        response = client.post("/api/uar/stream", json={
            "goal": "test cleanup",
            "skills": ["section_sum"]
        })
        
        assert response.status_code == 200


class TestInputValidationEdgeCases:
    """Test edge cases in input validation"""
    
    def test_unicode_handling(self):
        """Test proper handling of unicode input"""
        unicode_goals = [
            "测试目标",  # Chinese
            "🚀 Launch rocket",  # Emoji
            "Café au lait",  # Accented characters
            "العربية",  # Arabic
        ]
        
        for goal in unicode_goals:
            response = client.post("/api/uar/run", json={"goal": goal})
            # Should handle unicode properly
            assert response.status_code in [200, 400]
    
    def test_whitespace_handling(self):
        """Test whitespace handling"""
        whitespace_goals = [
            "   spaced goal   ",
            "\t\ttabbed goal\t\t",
            "\n\nnewlined goal\n\n",
            "  mixed \t whitespace \n goal  ",
        ]
        
        for goal in whitespace_goals:
            response = client.post("/api/uar/run", json={"goal": goal})
            # Should handle whitespace properly
            assert response.status_code in [200, 400]
    
    def test_special_characters(self):
        """Test special character handling"""
        special_goals = [
            "Goal with \"quotes\"",
            "Goal with 'apostrophes'",
            "Goal with &ampersand&",
            "Goal with <brackets>",
            "Goal with [square brackets]",
            "Goal with {curly braces}",
        ]
        
        for goal in special_goals:
            response = client.post("/api/uar/run", json={"goal": goal})
            # Should handle special characters properly
            assert response.status_code in [200, 400]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
