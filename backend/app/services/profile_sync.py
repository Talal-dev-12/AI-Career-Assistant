from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.db.models import Profile, UserSkill, User

def sync_profile_skills_to_user_skills(db: Session, user_id: str, skills: list[str]) -> None:
    """Syncs a flat list of skill strings (from Profile.data) into the relational user_skills table (MABD)."""
    # 1. Delete all existing relational skills for the user
    db.execute(delete(UserSkill).where(UserSkill.user_id == user_id))
    
    # 2. Add the new skills
    for skill_name in skills:
        if not skill_name.strip():
            continue
        db_skill = UserSkill(
            user_id=user_id,
            skill_name=skill_name.strip(),
            proficiency_level="Intermediate",
            years_experience=1.0
        )
        db.add(db_skill)
    db.flush()


def sync_user_skills_to_profile(db: Session, user_id: str) -> None:
    """Syncs relational user_skills (MABD) back into the profile JSON data block (Talha)."""
    # 1. Fetch all user skills
    skills = db.execute(
        select(UserSkill.skill_name).where(UserSkill.user_id == user_id)
    ).scalars().all()
    
    # 2. Fetch the user profile
    profile = db.execute(
        select(Profile).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
    
    if profile:
        profile_data = dict(profile.data or {})
        profile_data["skills"] = list(skills)
        profile.data = profile_data
        profile.version += 1
        db.flush()
