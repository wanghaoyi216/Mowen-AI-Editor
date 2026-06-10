import sys
sys.path.insert(0, '/app')
from app.db.base import SessionLocal
from app.models.chapter import Chapter
from app.models.project import NovelProject
db = SessionLocal()
chapters = db.query(Chapter).filter(Chapter.project_id == 1).order_by(Chapter.chapter_no.asc()).all()
project = db.query(NovelProject).filter(NovelProject.id == 1).first()
print(f"Project: {project.name}, genre={project.genre}")
for c in chapters:
    print(f'  Ch{c.chapter_no}: title="{c.title}"')
    print(f'    objective: "{c.objective}"')
    print(f'    conflict: "{c.conflict}"')
db.close()
