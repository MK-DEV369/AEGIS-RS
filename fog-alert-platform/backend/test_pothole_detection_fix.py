#!/usr/bin/env python
"""
Test script to verify pothole detection is saved to database.
This tests the fix where PotholeDetection.record_detection() is called.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from pathlib import Path
from fog_api.models import PotholeDetection
from django.utils import timezone
from datetime import timedelta

def test_database_detection():
    """Test that detection records exist in the database"""
    print("[TEST] Checking PotholeDetection records in database...")

    # Count all records
    all_records = PotholeDetection.objects.all()
    print(f"  Total records in database: {all_records.count()}")

    # Check recent records (last 5 minutes)
    recent_cutoff = timezone.now() - timedelta(minutes=5)
    recent_records = PotholeDetection.objects.filter(created_at__gte=recent_cutoff)
    print(f"  Records from last 5 minutes: {recent_records.count()}")

    if recent_records.exists():
        print("\n[SUCCESS] Recent detection records found!")
        for i, record in enumerate(recent_records[:3], 1):
            print(f"\n  Record {i}:")
            print(f"    - source_id: {record.source_id}")
            print(f"    - pothole_count: {record.pothole_count}")
            print(f"    - created_at: {record.created_at}")
            print(f"    - annotated_frame size: {len(record.annotated_frame) if record.annotated_frame else 0} bytes")
            print(f"    - latency_ms: {record.latency_ms}")
    else:
        print("\n[WARNING] No recent detection records found")
        print("  Possible causes:")
        print("  1. No frames have been sent to /api/pothole/predict/")
        print("  2. Predictions are failing")
        print("  3. Database not properly initialized")

        # Show status endpoint behavior
        print("\n[DEBUG] Checking status endpoint behavior...")
        from rest_framework.test import APIRequestFactory
        from fog_api.views import PotholeRuntimeStatusView

        factory = APIRequestFactory()
        view = PotholeRuntimeStatusView.as_view()
        request = factory.get('/api/pothole/status/')
        response = view(request)

        print(f"  Status endpoint response count: {response.data.get('count', 0)}")
        if response.data.get('items'):
            for item in response.data.get('items', [])[:1]:
                is_mock = item.get('_is_mock', False)
                print(f"  Data is mock: {is_mock}")
                if is_mock:
                    print("  [INFO] Mock data is being served (real data not in database)")

def test_status_endpoint():
    """Test that status endpoint returns detection data"""
    print("\n[TEST] Testing status endpoint...")

    from rest_framework.test import APIRequestFactory
    from fog_api.views import PotholeRuntimeStatusView

    factory = APIRequestFactory()
    view = PotholeRuntimeStatusView.as_view()
    request = factory.get('/api/pothole/status/?source_id=phone_pothole_01')
    response = view(request)

    data = response.data
    print(f"  Response status: {response.status_code}")
    print(f"  Response count: {data.get('count', 0)}")

    if data.get('items'):
        item = data['items'][0]
        print(f"  First item pothole_count: {item.get('pothole_count', 0)}")
        print(f"  First item is_mock: {item.get('_is_mock', False)}")
        return True
    else:
        print("  [WARNING] Status endpoint returned no items")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Pothole Detection Database Fix Verification")
    print("=" * 60)

    test_database_detection()
    test_status_endpoint()

    print("\n" + "=" * 60)
    print("Test complete. Check results above.")
    print("=" * 60)
