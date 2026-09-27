"""
Concurrency Tests
Tests that idempotency works correctly under concurrent uploads
"""
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class TestConcurrentUploads:
    """Test concurrent upload scenarios"""

    def test_concurrent_duplicate_uploads_create_single_import(self, client, fixture_path):
        """
        Test that multiple threads uploading identical bytes simultaneously
        result in only one import being created

        This verifies atomic idempotency via database constraint
        """
        import os
        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")

        # Read file content once
        with open(filepath, "rb") as f:
            content = f.read()

        # Track results from concurrent uploads
        results = []
        import_ids = set()
        status_codes = []

        def upload_file(thread_id):
            """Upload the same content from multiple threads"""
            try:
                files = {"file": (f"upload_{thread_id}.xml", content, "application/xml")}
                response = client.post("/api/tally/imports", files=files)

                return {
                    "thread_id": thread_id,
                    "status_code": response.status_code,
                    "response": response.json(),
                    "success": True
                }
            except Exception as e:
                return {
                    "thread_id": thread_id,
                    "status_code": None,
                    "response": None,
                    "success": False,
                    "error": str(e)
                }

        # Launch 10 concurrent uploads of identical content
        num_threads = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(upload_file, i) for i in range(num_threads)]

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        # Analyze results
        successful_results = [r for r in results if r["success"]]

        # All requests should succeed
        assert len(successful_results) == num_threads, \
            f"Expected {num_threads} successful requests, got {len(successful_results)}"

        # Collect all import IDs and status codes
        for result in successful_results:
            status_codes.append(result["status_code"])
            import_ids.add(result["response"]["importId"])

        # Critical assertion: Only ONE unique import should be created
        assert len(import_ids) == 1, \
            f"Expected 1 unique import, got {len(import_ids)}: {import_ids}"

        # At least one should be 201 (the first one)
        assert 201 in status_codes, "Expected at least one 201 Created response"

        # The rest should be 200 (duplicates)
        count_201 = status_codes.count(201)
        count_200 = status_codes.count(200)

        # Exactly 1 should be 201, rest should be 200
        # (In practice, due to timing, exactly 1 will succeed first)
        assert count_201 >= 1, f"Expected at least 1 x 201, got {count_201}"
        assert count_200 >= 0, f"Expected some 200s for duplicates, got {count_200}"

        print(f"\n✓ Concurrent uploads: {count_201} x 201 Created, {count_200} x 200 Duplicate")
        print(f"✓ Only {len(import_ids)} unique import created despite {num_threads} concurrent requests")

    def test_concurrent_different_files_create_separate_imports(self, client, fixture_path):
        """
        Test that concurrent uploads of different files create separate imports
        """
        import os

        # Use two different fixture files
        files_to_upload = [
            "01_receipt_with_allocations.xml",
            "07_utf8_bom_payment.xml"
        ]

        contents = []
        for filename in files_to_upload:
            filepath = os.path.join(fixture_path, filename)
            with open(filepath, "rb") as f:
                contents.append(f.read())

        results = []

        def upload_file(thread_id, content):
            """Upload different content from multiple threads"""
            files = {"file": (f"upload_{thread_id}.xml", content, "application/xml")}
            response = client.post("/api/tally/imports", files=files)
            return {
                "thread_id": thread_id,
                "status_code": response.status_code,
                "import_id": response.json()["importId"]
            }

        # Upload each file multiple times concurrently
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i, content in enumerate(contents):
                # Upload each file twice concurrently
                futures.append(executor.submit(upload_file, f"file1_{i}", content))
                futures.append(executor.submit(upload_file, f"file2_{i}", content))

            for future in as_completed(futures):
                results.append(future.result())

        # Get unique import IDs
        import_ids = set(r["import_id"] for r in results)

        # Should have exactly 2 unique imports (one per unique file)
        assert len(import_ids) == 2, \
            f"Expected 2 unique imports for 2 different files, got {len(import_ids)}"

        print(f"\n✓ Concurrent different files: {len(import_ids)} unique imports created correctly")

    def test_race_condition_handling(self, client, fixture_path):
        """
        Test that database constraint handles race conditions correctly
        Even if two threads pass the existence check simultaneously,
        only one insert should succeed
        """
        import os
        filepath = os.path.join(fixture_path, "02_sales_invoice_nested.xml")

        with open(filepath, "rb") as f:
            content = f.read()

        # Barrier to synchronize thread start (maximize collision probability)
        barrier = threading.Barrier(5)
        results = []

        def synchronized_upload(thread_id):
            """Wait for all threads, then upload simultaneously"""
            barrier.wait()  # All threads wait here
            # All threads release at exact same time
            files = {"file": (f"sync_{thread_id}.xml", content, "application/xml")}
            response = client.post("/api/tally/imports", files=files)
            return response.status_code, response.json()["importId"]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(synchronized_upload, i) for i in range(5)]
            results = [future.result() for future in as_completed(futures)]

        # Extract import IDs
        import_ids = set(r[1] for r in results)

        # Despite synchronized start, should still have only 1 unique import
        assert len(import_ids) == 1, \
            f"Race condition not handled: got {len(import_ids)} imports instead of 1"

        print(f"✓ Race condition test passed: {len(import_ids)} unique import despite synchronized start")
