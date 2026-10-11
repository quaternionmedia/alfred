from .project import Project, ProjectUpdate, RenderSettings
from .users import UserCreate, UserRead, UserUpdate

# Names, not objects.
#
# This read `__all__ = [Project, ProjectUpdate, ...]` -- the classes
# themselves. `from alfred.core.models import *` raises TypeError on that,
# because `__all__` must contain strings. Exactly the same defect was fixed in
# core/utils/__init__.py earlier on this branch; it was in two modules, and
# nothing caught either because no code in the repository uses a star import.
__all__ = [
    'Project',
    'ProjectUpdate',
    'RenderSettings',
    'UserRead',
    'UserCreate',
    'UserUpdate',
]
