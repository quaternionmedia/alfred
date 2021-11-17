from typing import Optional, List
from datetime import datetime
from beanie import Document

class Template(Document):
    logic: dict
    fields: Optional[List]
    class Config:
        title = 'Template Project'

class TemplateUpdate(Template):
    logic: Optional[dict]
    fields: Optional[List]
