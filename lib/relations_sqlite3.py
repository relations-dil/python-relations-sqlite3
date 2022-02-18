"""
Module for intersting with sqlite3
"""

# pylint: disable=arguments-differ,unsupported-membership-test

import glob
import copy
import json

import sqlite3

import relations
import relations_sql
import relations_sqlite

class Source(relations.Source): # pylint: disable=too-many-public-methods
    """
    sqlite3 Source
    """

    SQL = relations_sql.SQL
    ASC = relations_sql.ASC
    DESC = relations_sql.DESC

    LIKE = relations_sqlite.LIKE
    IN = relations_sqlite.IN
    OR = relations_sqlite.OR
    OP = relations_sqlite.OP

    AS = relations_sqlite.AS
    FIELDS = relations_sqlite.FIELDS
    TABLE = relations_sqlite.TABLE
    TABLE_NAME = relations_sqlite.TABLE_NAME

    INSERT = relations_sqlite.INSERT
    SELECT = relations_sqlite.SELECT
    UPDATE = relations_sqlite.UPDATE
    DELETE = relations_sqlite.DELETE

    KIND = "sqlite"

    database = None   # Database to use
    connection = None # Connection
    created = False   # If we created the connection

    def __init__(self, name, database, connection=None, schemas=None, **kwargs):

        self.database = database
        self.schemas = schemas if schemas is not None else {}
        self.schema = self.schemas.get('main')

        if connection is not None:
            self.connection = connection
        else:
            self.created = True

            self.connection = sqlite3.connect(
                self.database,
                **{name: arg for name, arg in kwargs.items() if name not in ["name", "database", "schemas", "connection"]}
            )

            cursor = self.connection.cursor()
            for schema in sorted(self.schemas.keys()):
                if schema != 'main':
                    cursor.execute(f"ATTACH DATABASE '{self.schemas[schema]}' AS `{schema}`")

        self.connection.row_factory = sqlite3.Row

    def __del__(self):

        if self.created and self.connection:
            self.connection.close()

    def execute(self, commands):
        """
        Execute SQL
        """

        if isinstance(commands, relations_sql.SQL):
            commands.generate()
            commands = commands.sql

        if not isinstance(commands, list):
            commands = commands.split(";\n")

        cursor = self.connection.cursor()

        for command in commands:
            if command.strip():
                cursor.execute(command)

        self.connection.commit()

        cursor.close()

    def init(self, model):
        """
        Init the model
        """

        self.record_init(model._fields)

        self.ensure_attribute(model, "SCHEMA")
        self.ensure_attribute(model, "STORE")

        if model.SCHEMA is None:
            model.SCHEMA = self.schema

        if model.STORE is None:
            model.STORE = model.NAME

        if model._id is not None and model._fields._names[model._id].auto is None and model._fields._names[model._id].kind == int:
            model._fields._names[model._id].auto = True

    def define(self, migration=None, definition=None):
        """
        Creates the DDL for a model
        """

        ddl = self.TABLE(migration, definition)
        ddl.generate(indent=2)

        return ddl.sql

    def create_query(self, model):
        """
        Get query for what's being inserted
        """

        fields = [field.store for field in model._fields._order if not field.auto and not field.inject]
        query = self.INSERT(self.TABLE_NAME(model.STORE, schema=model.SCHEMA), *fields)

        if not model._bulk and model._id is not None and model._fields._names[model._id].auto:
            if model._mode == "many":
                raise relations.ModelError(model, "only one create query at a time")
            return copy.deepcopy(query).VALUES(**model._record.create({})).bind(model)

        for creating in model._each("create"):
            query.VALUES(**creating._record.create({}))

        return query

    @staticmethod
    def create_id(cursor, model, query):
        """
        Inserts a single record and sets the id
        """

        query.generate()
        cursor.execute(query.sql, tuple(query.args))

        model[model._id] = cursor.lastrowid

    def create(self, model, query=None):
        """
        Executes the create
        """

        cursor = self.connection.cursor()

        if not model._bulk and model._id is not None and model._fields._names[model._id].auto:
            for creating in model._each("create"):
                create_query = query or self.create_query(creating)
                self.create_id(cursor, creating, create_query)
        else:
            create_query = query or self.create_query(model)
            create_query.generate()
            cursor.execute(create_query.sql, tuple(create_query.args))

        cursor.close()

        if not model._bulk:

            for creating in model._each("create"):
                for parent_child in creating.CHILDREN:
                    if creating._children.get(parent_child):
                        creating._children[parent_child].create()
                creating._action = "update"
                creating._record._action = "update"

            model._action = "update"

        else:

            model._models = []

        return model

    def retrieve_field(self, field, query):
        """
        Adds where caluse to query
        """

        for operator, value in (field.criteria or {}).items():
            name = f"{field.store}__{operator}"
            extracted = operator.rsplit("__", 1)[0] in (field.extract or {})
            query.WHERE(self.OP(name, value, EXTRACTED=extracted))

    def like(self, model, query):
        """
        Adds like information to the query
        """

        if model._like is None:
            return

        titles = self.OR()

        for name in model._titles:

            path = name.split("__", 1)
            name = path.pop(0)

            field = model._fields._names[name]

            parent = False

            for relation in model.PARENTS.values():
                if field.name == relation.child_field:
                    parent = relation.Parent.many(like=model._like).limit(model._chunk)
                    if parent[relation.parent_field]:
                        titles(self.IN(field.store, parent[relation.parent_field]))
                        model.overflow = model.overflow or parent.overflow
                    else:
                        parent = True

            if not parent:

                paths = path if path else field.titles

                if paths:
                    for path in paths:
                        titles(self.LIKE(f"{field.store}__{path}", model._like, extracted=path in (field.extract or {})))
                else:
                    titles(self.LIKE(field.store, model._like))

        if titles:
            query.WHERE(titles)

    def sort(self, model, query):
        """
        Adds sort information to the query
        """

        for field in (model._sort or model._order or []):
            query.ORDER_BY(**{field[1:]: (self.ASC if field[0] == "+" else self.DESC)})

        model._sort = None

    @staticmethod
    def limit(model, query):
        """
        Adds sort informaiton to the query
        """

        if model._limit is not None:
            query.LIMIT(model._limit)

        if model._offset:
            query.LIMIT(model._offset)

    def count_query(self, model):
        """
        Get query for what's being inserted
        """

        query = self.SELECT(self.AS("total", self.SQL("COUNT(*)"))).FROM(self.TABLE_NAME(model.STORE, schema=model.SCHEMA))

        model._collate()
        self.retrieve_record(model._record, query)
        self.like(model, query)

        return query

    def retrieve_query(self, model):
        """
        Get query for what's being inserted
        """

        query = self.count_query(model)

        query.FIELDS = self.FIELDS("*")

        self.sort(model, query)
        self.limit(model, query)

        return query

    def titles_query(self, model):
        """
        Get query for what's being selected
        """

        return self.retrieve_query(model)

    def count(self, model, query=None):
        """
        Executes the count
        """

        cursor = self.connection.cursor()

        if query is None:
            query = self.count_query(model)

        query.generate()

        cursor.execute(query.sql, query.args)

        total = cursor.fetchone()["total"] if cursor.rowcount else 0

        cursor.close()

        return total

    @staticmethod
    def values_retrieve(model, values):
        """
        Encodes the fields in json if needed
        """
        for field in model._fields._order:
            if isinstance(values.get(field.store), str) and field.kind not in [bool, int, float, str]:
                values[field.store] = json.loads(values[field.store])

        return values

    def retrieve(self, model, verify=True, query=None):
        """
        Executes the retrieve
        """

        cursor = self.connection.cursor()

        if query is None:
            query = self.retrieve_query(model)

        query.generate()

        cursor.execute(query.sql, tuple(query.args))

        rows = cursor.fetchall()

        if model._mode == "one" and len(rows) > 1:
            raise relations.ModelError(model, "more than one retrieved")

        if model._mode == "one" and model._role != "child":

            if len(rows) < 1:

                if verify:
                    raise relations.ModelError(model, "none retrieved")
                return None

            model._record = model._build("update", _read=self.values_retrieve(model, dict(rows[0])))

        else:

            model._models = []

            for row in rows:
                model._models.append(model.__class__(_read=self.values_retrieve(model, dict(row))))

            if model._limit is not None:
                model.overflow = model.overflow or len(model._models) >= model._limit

            model._record = None

        model._action = "update"

        cursor.close()

        return model

    def titles(self, model, query=None):
        """
        Creates the titles structure
        """

        if model._action == "retrieve":
            self.retrieve(model, query=query)

        titles = relations.Titles(model)

        for titling in model._each():
            titles.add(titling)

        return titles

    def update_field(self, field, updates, query):
        """
        Adds fields to update clause
        """

        if field.store in updates and not field.auto:
            query.SET(**{field.store: updates[field.store]})

    def update_query(self, model):
        """
        Create the update query
        """

        query = self.UPDATE(self.TABLE_NAME(model.STORE, schema=model.SCHEMA))

        if model._action == "retrieve" and model._record._action == "update":

            self.update_record(model._record, model._record.mass({}), query)

        elif model._id:

            if model._mode == "many":
                raise relations.ModelError(model, "only one update query at a time")

            self.update_record(model._record, model._record.update({}), query)

            query.WHERE(**{model._fields._names[model._id].store: model[model._id]})

        else:

            raise relations.ModelError(model, "nothing to update from")

        self.retrieve_record(model._record, query)

        return query

    def update(self, model, query=None):
        """
        Executes the update
        """

        cursor = self.connection.cursor()

        updated = 0

        # If the overall model is retrieving and the record has values set

        if model._action == "retrieve" and model._record._action == "update":

            update_query = query or self.update_query(model)

            update_query.generate()
            cursor.execute(update_query.sql, update_query.args)
            updated = cursor.rowcount

        elif model._id:

            for updating in model._each("update"):

                update_query = query or self.update_query(updating)

                if update_query.SET:

                    update_query.generate()
                    cursor.execute(update_query.sql, update_query.args)

                for parent_child in updating.CHILDREN:
                    if updating._children.get(parent_child):
                        updating._children[parent_child].create().update()

                updated += cursor.rowcount

        else:

            raise relations.ModelError(model, "nothing to update from")

        return updated

    def delete_query(self, model):
        """
        Create the update query
        """

        query = self.DELETE(self.TABLE_NAME(model.STORE, schema=model.SCHEMA))

        if model._action == "retrieve":

            self.retrieve_record(model._record, query)

        elif model._id:

            ids = []
            store = model._fields._names[model._id].store
            for deleting in model._each():
                ids.append(deleting[model._id])
            query.WHERE(**{f"{store}__in": ids})

        else:

            raise relations.ModelError(model, "nothing to delete from")

        return query

    def delete(self, model, query=None):
        """
        Executes the delete
        """

        cursor = self.connection.cursor()

        delete_query = query or self.delete_query(model)

        delete_query.generate()
        cursor.execute(delete_query.sql, tuple(delete_query.args))

        return cursor.rowcount

    def definition(self, file_path, source_path):
        """"
        Converts a definition file to a MySQL definition file
        """

        definitions = []

        with open(file_path, "r") as definition_file:
            definition = json.load(definition_file)
            for name in sorted(definition.keys()):
                if definition[name]["source"] == self.name:
                    definitions.append(self.define(definition[name]))

        if definitions:
            file_name = file_path.split("/")[-1].split('.')[0]
            with open(f"{source_path}/{file_name}.sql", "w") as source_file:
                source_file.write("\n".join(definitions))

    def migration(self, file_path, source_path):
        """"
        Converts a migration file to a source definition file
        """

        migrations = []

        with open(file_path, "r") as migration_file:
            migration = json.load(migration_file)

            for add in sorted(migration.get('add', {}).keys()):
                if migration['add'][add]["source"] == self.name:
                    migrations.append(self.define(migration['add'][add]))

            for remove in sorted(migration.get('remove', {}).keys()):
                if migration['remove'][remove]["source"] == self.name:
                    migrations.append(self.define(definition=migration['remove'][remove]))

            for change in sorted(migration.get('change', {}).keys()):
                if migration['change'][change]['definition']["source"] == self.name:
                    migrations.append(
                        self.define(migration['change'][change]['migration'], migration['change'][change]['definition'])
                    )

        if migrations:
            file_name = file_path.split("/")[-1].split('.')[0]
            with open(f"{source_path}/{file_name}.sql", "w") as source_file:
                source_file.write("\n".join(migrations))

    def load(self, load_path):
        """
        Load a file
        """

        with open(load_path, 'r') as load_file:
            self.execute(load_file.read().split(";\n"))

    def list(self, source_path):
        """
        List the migration by pairs
        """

        migrations = {}

        for file_path in glob.glob(f"{source_path}/*-*.sql"):

            file_name = file_path.rsplit("/", 1)[-1]
            kind, stamp = file_name.split('.')[0].split('-', 1)

            migrations.setdefault(stamp, {})
            migrations[stamp][kind] = file_name

        return migrations

    def migrate(self, source_path):
        """
        Migrate all the existing files to where we are
        """

        class Migration(relations.Model):
            """
            Model for migrations
            """

            SOURCE = self.name
            STORE = "_relations_migration"
            UNIQUE = False

            stamp = str

        migrated = False

        self.execute(Migration.define())

        stamps = Migration.many().stamp

        migration_paths = sorted(glob.glob(f"{source_path}/migration-*.sql"))

        if not stamps:

            migration = Migration().bulk().add("definition")

            for migration_path in migration_paths:
                stamp = migration_path.rsplit("/migration-", 1)[-1].split('.')[0]
                migration.add(stamp)

            migration.create()
            self.connection.commit()
            self.load(f"{source_path}/definition.sql")
            migrated = True

        else:

            for migration_path in migration_paths:
                stamp = migration_path.rsplit("/migration-", 1)[-1].split('.')[0]
                if stamp not in stamps:
                    Migration(stamp).create()
                    self.connection.commit()
                    self.load(migration_path)
                    migrated = True

        return migrated
