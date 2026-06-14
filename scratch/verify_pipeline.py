import httpx
import json

BASE_URL = "http://localhost:8000"

def audit_pipeline():
    print("=== Career Pipeline Functional Audit ===")
    
    # 1. Create a test user
    print("\n[Step 1] Creating a test user...")
    user_payload = {
        "email": "jane.doe.audit@example.com",
        "full_name": "Jane Doe"
    }
    try:
        resp = httpx.post(f"{BASE_URL}/users", json=user_payload)
        resp.raise_for_status()
        user_data = resp.json()
        print(f"Status: Success (HTTP {resp.status_code})")
        print(f"Output: {json.dumps(user_data, indent=2)}")
        user_id = user_data.get("id") or user_data.get("user_id")
    except Exception as e:
        print(f"Status: Failed")
        print(f"Error: {e}")
        return

    # 2. Upload a sample CV
    print("\n[Step 2] Uploading a sample CV...")
    cv_content = """
    Jane Doe
    jane.doe@example.com
    +1-555-0199
    
    Professional Experience:
    Senior React Developer at Vercel (June 2024 - Present)
    - Optimized next.js rendering pipelines, leading to 25% faster hydration.
    - Led architectural design for React Server Components (RSC).
    - Skilled in TypeScript, JavaScript, CSS, HTML5, and Git.
    
    Frontend Engineer at Stripe (Jan 2023 - May 2024)
    - Maintained payment dashboards with React and Redux state management.
    
    Education:
    Bachelor of Computer Science from DHA Suffa University (Class of 2025)
    
    Target Roles:
    Senior React Developer, Frontend Engineer, Software Engineer
    """
    
    try:
        files = {
            "file": ("jane_doe_cv.txt", cv_content.encode("utf-8"), "text/plain")
        }
        resp = httpx.post(f"{BASE_URL}/users/{user_id}/cv", files=files)
        resp.raise_for_status()
        cv_data = resp.json()
        print(f"Status: Success (HTTP {resp.status_code})")
        print(f"Output: {json.dumps(cv_data, indent=2)}")
    except Exception as e:
        print(f"Status: Failed")
        print(f"Error: {e}")
        return

    # 3. Query job listings
    print("\n[Step 3] Fetching job listings...")
    try:
        resp = httpx.get(f"{BASE_URL}/jobs")
        resp.raise_for_status()
        jobs = resp.json()
        print(f"Status: Success (HTTP {resp.status_code})")
        print(f"Total Jobs Found: {len(jobs)}")
        print(f"Jobs: {json.dumps(jobs[:3], indent=2)}")
        if not jobs:
            print("No jobs in database to match.")
            return
        target_job_id = jobs[0]["id"]
    except Exception as e:
        print(f"Status: Failed")
        print(f"Error: {e}")
        return

    # 4. Job Matching
    print(f"\n[Step 4] Matching user {user_id} with all jobs...")
    for job in jobs:
        job_id = job["id"]
        title = job["title"]
        company = job["company"]
        print(f"\nMatching user {user_id} with job: {title} @ {company} ({job_id})...")
        try:
            resp = httpx.get(f"{BASE_URL}/users/{user_id}/jobs/{job_id}/match")
            resp.raise_for_status()
            match_data = resp.json()
            print(f"Status: Success (HTTP {resp.status_code})")
            print(f"Match Output: {json.dumps(match_data, indent=2)}")
        except Exception as e:
            print(f"Status: Failed")
            print(f"Error: {e}")

    print("\n=== Audit Run Complete ===")

if __name__ == "__main__":
    audit_pipeline()
