"""
Database routers for QueueMe application.

These routers handle the routing of database operations to the appropriate database connection
based on the type of operation (read/write) and model.
"""

import random

from django.conf import settings


class ReplicationRouter:
    """
    Database router for read/write splitting.

    This router sends all write operations to the primary database
    and distributes read operations across replicas.
    """

    def _is_read_method(self, method_name):
        """Check if the method is a read operation"""
        return method_name.startswith(
            (
                "get",
                "filter",
                "count",
                "exists",
                "aggregate",
                "latest",
                "earliest",
                "first",
                "last",
                "in_bulk",
                "values",
                "values_list",
                "dates",
                "datetimes",
                "explain",
                "raw",
                "select_related",
                "prefetch_related",
                "annotate",
                "order_by",
            )
        )

    def _get_read_db(self):
        """
        Get a read database connection.
        Uses a round-robin approach for load balancing across replicas.
        """
        replicas = [db for db in settings.DATABASES.keys() if db.startswith("replica")]
        if not replicas:
            return "default"

        return random.choice(replicas)

    def db_for_read(self, model, **hints):
        """
        Route read operations to a read replica.
        """
        # Always route to primary for models that need consistency
        if hasattr(model, "requires_primary_db") and model.requires_primary_db:
            return "default"

        # Check if we're in a transaction - must use primary
        if (
            hints.get("instance")
            and hasattr(hints["instance"], "_state")
            and hints["instance"]._state.db
        ):
            return hints["instance"]._state.db

        # Otherwise use a read replica
        return self._get_read_db()

    def db_for_write(self, model, **hints):
        """
        Route write operations to the primary database.
        """
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects in any database.
        """
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Only allow migrations on the primary database.
        """
        return db == "default"

    def allow_syncdb(self, db, model):
        """
        Only allow sync on the primary database.
        """
        return db == "default"
