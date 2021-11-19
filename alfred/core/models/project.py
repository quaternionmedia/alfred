from typing import Optional, List
from datetime import datetime
from beanie import Document

class Project(Document):
    logic: dict
    fields: Optional[List]
    class Config:
        title = 'Project Project'

class ProjectUpdate(Project):
    logic: Optional[dict]
    fields: Optional[List]
