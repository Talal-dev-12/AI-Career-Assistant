import sys
import os
import argparse
import asyncio
from datetime import datetime

# Proactor event loop is required on Windows for crawl4ai/playwright subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Setup sys.path to resolve imports correctly
backend_dir = os.path.dirname(os.path.abspath(__file__))
scrappping_dir = os.path.join(backend_dir, "scrappping")

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if scrappping_dir not in sys.path:
    sys.path.insert(0, scrappping_dir)

from app.db.database import get_session, init_db
from app.db.models import Job
from agents.job_scraping_agent import JobScrapingAgent
from agents.job_verification_agent import JobVerificationAgent

async def run_pipeline(keyword: str, location: str, platforms: list[str], max_pages: int):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing database...")
    init_db()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing scraping and verification agents...")
    scraping_agent = JobScrapingAgent()
    verification_agent = JobVerificationAgent()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting scrape: keyword='{keyword}', location='{location}', platforms={platforms}, max_pages={max_pages}")
    
    # 1. Run Scraper
    scrape_result = await scraping_agent.scrape_jobs(
        keyword=keyword,
        location=location,
        platforms=platforms,
        max_pages=max_pages
    )
    
    jobs = scrape_result.get("jobs", [])
    total_scraped = len(jobs)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scrape finished. Found {total_scraped} jobs.")

    if not jobs:
        print("No jobs scraped. Exiting.")
        return

    # 2. Run Verification Agent
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running verification pipeline...")
    verified_jobs = verification_agent.verify_jobs(jobs)
    
    # 3. Save to database
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Saving jobs to database...")
    db_session_gen = get_session()
    db = next(db_session_gen)
    
    saved_count = 0
    verified_count = 0
    
    try:
        for job_data in verified_jobs:
            verified_status = job_data.get("verified_status", "flagged_for_review")
            is_verified = (verified_status == "verified")
            
            # Extract salary if available
            salary_str = job_data.get("salary", "")
            salary_min = None
            salary_max = None
            if salary_str:
                import re
                nums = [float(s.replace(",", "")) for s in re.findall(r'\b\d+(?:,\d+)?\b', salary_str)]
                if len(nums) >= 2:
                    salary_min = nums[0]
                    salary_max = nums[1]
                elif len(nums) == 1:
                    salary_min = nums[0]

            # Parse date_posted if available
            posted_at = None
            date_posted_str = job_data.get("date_posted", "")
            if date_posted_str:
                try:
                    posted_at = datetime.strptime(date_posted_str, "%Y-%m-%d")
                except Exception:
                    posted_at = datetime.utcnow()
            else:
                posted_at = datetime.utcnow()

            from sqlalchemy import select
            existing_job = db.execute(
                select(Job).where(Job.external_id == job_data["job_id"])
            ).scalar_one_or_none()

            if existing_job:
                # Update fields
                existing_job.title = job_data.get("title", existing_job.title)
                existing_job.company = job_data.get("company", existing_job.company)
                existing_job.company_name = job_data.get("company", existing_job.company_name)
                existing_job.location = job_data.get("location", existing_job.location)
                existing_job.url = job_data.get("apply_link") or job_data.get("source_url") or existing_job.url
                existing_job.description = job_data.get("description", existing_job.description)
                existing_job.required_skills = job_data.get("required_skills", existing_job.required_skills)
                existing_job.verified = is_verified
                existing_job.verification_reasons = job_data.get("verification_details")
                if salary_min:
                    existing_job.salary_min = salary_min
                if salary_max:
                    existing_job.salary_max = salary_max
                if posted_at:
                    existing_job.posted_at = posted_at
            else:
                new_job = Job(
                    external_id=job_data["job_id"],
                    source=job_data.get("platform", "scraper"),
                    title=job_data.get("title", ""),
                    company=job_data.get("company", ""),
                    company_name=job_data.get("company", ""),
                    location=job_data.get("location", ""),
                    url=job_data.get("apply_link") or job_data.get("source_url", ""),
                    description=job_data.get("description", ""),
                    required_skills=job_data.get("required_skills", []),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    posted_at=posted_at,
                    verified=is_verified,
                    verification_reasons=job_data.get("verification_details")
                )
                db.add(new_job)
            
            saved_count += 1
            if is_verified:
                verified_count += 1

        db.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Database transaction committed.")
    except Exception as e:
        db.rollback()
        print(f"Error saving to database: {e}")
        raise e
    finally:
        db.close()

    print("\n" + "="*50)
    print("SCRAPING AND VERIFICATION RUN SUMMARY")
    print("="*50)
    print(f"Total jobs scraped: {total_scraped}")
    print(f"Total jobs verified (legitimate): {verified_count}")
    print(f"Total jobs flagged/rejected: {saved_count - verified_count}")
    print(f"Total records saved/updated in DB: {saved_count}")
    print("="*50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Job Scraping and Verification pipeline.")
    parser.add_argument("--keyword", type=str, default="React Developer", help="Search keyword")
    parser.add_argument("--location", type=str, default="", help="Location filter")
    parser.add_argument("--platforms", type=str, default="indeed,linkedin", help="Comma-separated platforms")
    parser.add_argument("--max-pages", type=str, default="1", help="Max pages to scrape")
    
    args = parser.parse_args()
    
    platforms_list = [p.strip() for p in args.platforms.split(",") if p.strip()]
    
    try:
        max_pages_int = int(args.max_pages)
    except ValueError:
        max_pages_int = 1

    asyncio.run(run_pipeline(
        keyword=args.keyword,
        location=args.location,
        platforms=platforms_list,
        max_pages=max_pages_int
    ))
