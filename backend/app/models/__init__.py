"""Import every ORM model module here so that Base.metadata is always
fully populated, regardless of which individual model a caller imports
first.

Several models declare string-based ForeignKey references to tables
defined in *other* model modules (e.g. AuditRecord.execution_id ->
"automation_executions", owned by app.models.execution). SQLAlchemy only
resolves those string references against tables that have actually been
registered on Base.metadata at mapper-configuration time. If a caller
imports e.g. ``app.models.audit`` directly without ``app.models.execution``
having been imported anywhere else in the process, the first flush touching
an AuditRecord raises ``NoReferencedTableError`` even though the schema
itself (and the actual database, via Alembic) is correct.

Importing the ``app.models`` package (this file) guarantees every model is
registered together, so ``from app.models.audit import AuditRecord`` and
``import app.models`` both leave Base.metadata in the same state.
"""

from app.models import admission  # noqa: F401
from app.models import audit  # noqa: F401
from app.models import execution  # noqa: F401
from app.models import fee  # noqa: F401
from app.models import student  # noqa: F401
