"""
Module for intersting with sqlite3
"""

# pylint: disable=arguments-differ

import copy
import json

import sqlite3

import relations
import relations.query

class Source(relations.Source):
    """
    sqlite3 Source
    """

    RETRIEVE = {
        'eq': '=',
        'gt': '>',
        'gte': '>=',
        'lt': '<',
        'lte': '<='
    }

    database = None   # Database to use
    connection = None # Connection
    created = False   # If we created the connection

    def __init__(self, name, database, connection=None, **kwargs):

        self.database = database

        if connection is not None:
            self.connection = connection
        else:
            self.created = True
            self.connection = sqlite3.connect(
                self.database,
                **{name: arg for name, arg in kwargs.items() if name not in ["name", "database", "connection"]}
            )

        self.connection.row_factory = sqlite3.Row

    def __del__(self):

        if self.created and self.connection:
            self.connection.close()

    @staticmethod
    def table(model):
        """
        Get the full table name
        """

        table = []

        if model.DATABASE is not None:
            table.append(model.DATABASE)

        table.append(model.TABLE)

        return f"`{'___'.join(table)}`"

    @staticmethod
    def encode(model, values):
        """
        Encodes the fields in json if needed
        """

        encoded = []

        for field in model._fields._order:
            if field.readonly or field.inject:
                continue
            if values.get(field.store) is not None and field.kind not in [bool, int, float, str]:
                encoded.append(json.dumps(values[field.store]))
            else:
                encoded.append(values[field.store])

        return encoded

    @staticmethod
    def decode(model, values):
        """
        Encodes the fields in json if needed
        """
        for field in model._fields._order:
            if values.get(field.store) is not None and field.kind not in [bool, int, float, str]:
                values[field.store] = json.loads(values[field.store])

        return values

    @staticmethod
    def walk(path):
        """
        Generates the JSON pathing for a field
        """

        if isinstance(path, str):
            path = path.split('__')

        places = []

        for place in path:

            if relations.INDEX.match(place):
                places.append(f"[{int(place)}]")
            elif place[0] == '_':
                places.append(f'."{place[1:]}"')
            else:
                places.append(f".{place}")

        return f"${''.join(places)}"

    def field_init(self, field):
        """
        Make sure there's primary_key and definition
        """

        self.ensure_attribute(field, "primary_key")
        self.ensure_attribute(field, "definition")

    def model_init(self, model):
        """
        Init the model
        """

        self.record_init(model._fields)

        self.ensure_attribute(model, "DATABASE")
        self.ensure_attribute(model, "TABLE")
        self.ensure_attribute(model, "QUERY")
        self.ensure_attribute(model, "DEFINITION")

        if model.TABLE is None:
            model.TABLE = model.NAME

        if model.QUERY is None:
            model.QUERY = relations.query.Query(selects='*', froms=self.table(model))

        if model._id is not None and model._fields._names[model._id].primary_key is None:
            model._fields._names[model._id].primary_key = True
            model._fields._names[model._id].readonly = True

    def field_define(self, field, definitions, model): # pylint: disable=too-many-branches
        """
        Add what this field is the definition
        """

        if field.inject:
            return

        if field.definition is not None:
            definitions.append(field.definition)
            return

        definition = [f"`{field.store}`"]

        default = None

        if field.kind == bool:

            definition.append("INTEGER")

            if field.default is not None and not callable(field.default):
                default = f"DEFAULT {int(field.default)}"

        elif field.kind == int:

            definition.append("INTEGER")

            if field.default is not None and not callable(field.default):
                default = f"DEFAULT {field.default}"

        elif field.kind == float:

            definition.append("REAL")

            if field.default is not None and not callable(field.default):
                default = f"DEFAULT {field.default}"

        elif field.kind == str:

            definition.append("TEXT")

            if field.default is not None and not callable(field.default):
                default = f"DEFAULT '{field.default}'"

        else:

            definition.append("TEXT")

        if not field.none:
            definition.append("NOT NULL")

        if field.primary_key:
            definition.append("PRIMARY KEY")

        if default:
            definition.append(default)

        if field.extract:
            path = field.extract.split('__')
            extracted = model._fields._names[path.pop(0)]
            definition.append(f"AS (json_extract(`{extracted.store}`,'{self.walk(path)}'))")

        definitions.append(" ".join(definition))

    def model_define(self, cls):

        model = cls.thy()

        if model.DEFINITION is not None:
            return model.DEFINITION

        definitions = []

        self.record_define(model._fields, definitions, model)

        sep = ',\n  '

        statements = [
            f"CREATE TABLE IF NOT EXISTS {self.table(model)} (\n  {sep.join(definitions)}\n)"
        ]

        for unique in model._unique:
            name = f"{model.TABLE}_{unique.replace('-', '_')}"
            fields = '`,`'.join(model._unique[unique])
            statements.append(f'CREATE UNIQUE INDEX `{name}` ON {self.table(model)} (`{fields}`)')

        for index in model._index:
            name = f"{model.TABLE}_{index.replace('-', '_')}"
            fields = '`,`'.join(model._index[index])
            statements.append(f'CREATE INDEX `{name}` ON {self.table(model)} (`{fields}`)')

        return statements

    def field_create(self, field, fields, clause):
        """
        Adds values to clause if not readonly
        """

        if not field.readonly and not field.inject:
            fields.append(f"`{field.store}`")
            clause.append("?")
            field.changed = False

    def model_create(self, model):
        """
        Executes the create
        """

        cursor = self.connection.cursor()

        # Create the insert query

        fields = []
        clause = []

        self.record_create(model._fields, fields, clause)

        query = f"INSERT INTO {self.table(model)} ({','.join(fields)}) VALUES({','.join(clause)})"

        if not model._bulk and model._id is not None and model._fields._names[model._id].primary_key:
            for creating in model._each("create"):
                cursor.execute(query, self.encode(creating, creating._record.write({})))
                creating[model._id] = cursor.lastrowid
        else:
            cursor.executemany(query, [
                self.encode(creating, creating._record.write({})) for creating in model._each("create")
            ])

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

    def field_retrieve(self, field, query, values): # pylint: disable=too-many-branches
        """
        Adds where caluse to query
        """

        for operator, value in (field.criteria or {}).items():

            if operator not in relations.Field.OPERATORS:


                path = operator.split("__")
                operator = path.pop()

                values.append(self.walk(path))
                store = f"json_extract(`{field.store}`,?)"

            else:

                store = f"`{field.store}`"

            if operator == "in":
                query.add(wheres=f"{store} IN ({','.join(['?' for each in value])})")
                values.extend(value)
            elif operator == "ne":
                query.add(wheres=f"{store} NOT IN ({','.join(['?' for each in value])})")
                values.extend(value)
            elif operator == "like":
                query.add(wheres=f'{store} LIKE ?')
                values.append(f"%{value}%")
            elif operator == "notlike":
                query.add(wheres=f'{store} NOT LIKE ?')
                values.append(f"%{value}%")
            elif operator == "null":
                query.add(wheres=f'{store} {"IS" if value else "IS NOT"} NULL')
            else:
                query.add(wheres=f"{store}{self.RETRIEVE[operator]}?")
                values.append(value)

    @classmethod
    def model_like(cls, model, query, values):
        """
        Adds like information to the query
        """

        if model._like is None:
            return

        ors = []

        for name in model._label:

            path = name.split("__", 1)
            name = path.pop(0)

            field = model._fields._names[name]

            parent = False

            for relation in model.PARENTS.values():
                if field.name == relation.child_field:
                    parent = relation.Parent.many(like=model._like).limit(model._chunk)
                    ors.append(f'`{field.store}` IN ({",".join(["?" for each in parent[relation.parent_field]])})')
                    values.extend(parent[relation.parent_field])
                    model.overflow = model.overflow or parent.overflow

            if not parent:

                paths = [path] if path else field.label

                if paths:

                    for path in paths:

                        ors.append(f"json_extract(`{field.store}`,?) LIKE ?")
                        values.append(cls.walk(path))
                        values.append(f"%{model._like}%")

                else:

                    ors.append(f'`{field.store}` LIKE ?')
                    values.append(f"%{model._like}%")

        query.add(wheres="(%s)" % " OR ".join(ors))

    @staticmethod
    def model_sort(model, query):
        """
        Adds sort information to the query
        """

        sort = model._sort or model._order

        if sort:
            order_bys = []
            for field in sort:
                order_bys.append(f'`{field[1:]}`' if field[0] == "+" else f'`{field[1:]}` DESC')
            query.add(order_bys=order_bys)

        model._sort = None

    @staticmethod
    def model_limit(model, query, values):
        """
        Adds limit informaiton to the query
        """

        if model._limit is None:
            return

        if model._offset:
            query.add(limits="? OFFSET ?")
            values.extend([model._limit, model._offset])
        else:
            query.add(limits="?")
            values.append(model._limit)

    def model_retrieve(self, model, verify=True):
        """
        Executes the retrieve
        """

        model._collate()

        cursor = self.connection.cursor()

        query = copy.deepcopy(model.QUERY)
        values = []

        self.record_retrieve(model._record, query, values)

        self.model_like(model, query, values)
        self.model_sort(model, query)
        self.model_limit(model, query, values)

        cursor.execute(query.get(), values)

        rows = cursor.fetchall()

        if model._mode == "one" and len(rows) > 1:
            raise relations.ModelError(model, "more than one retrieved")

        if model._mode == "one" and model._role != "child":

            if len(rows) < 1:

                if verify:
                    raise relations.ModelError(model, "none retrieved")
                return None

            model._record = model._build("update", _read=self.decode(model, dict(rows[0])))

        else:

            model._models = []

            for row in rows:
                model._models.append(model.__class__(_read=self.decode(model, dict(row))))

            if model._limit is not None:
                model.overflow = model.overflow or len(model._models) >= model._limit

            model._record = None

        model._action = "update"

        cursor.close()

        return model

    def model_labels(self, model):
        """
        Creates the labels structure
        """

        if model._action == "retrieve":
            self.model_retrieve(model)

        labels = relations.Labels(model)

        for labeling in model._each():
            labels.add(labeling)

        return labels

    def field_update(self, field, clause, values, changed=None):
        """
        Preps values to dict (if not readonly)
        """

        if not field.readonly and not field.inject:
            if field.replace and not field.changed:
                field.value = field.default() if callable(field.default) else field.default
            if changed is None or field.changed == changed:
                clause.append(f"`{field.store}`=?")
                if field.kind in [list, dict] and field.value is not None:
                    values.append(json.dumps(field.value))
                else:
                    values.append(field.value)
                field.changed = False

    def model_update(self, model):
        """
        Executes the update
        """

        cursor = self.connection.cursor()

        updated = 0

        # If the overall model is retrieving and the record has values set

        if model._action == "retrieve" and model._record._action == "update":

            # Build the SET clause first

            clause = []
            values = []

            self.record_update(model._record, clause, values, changed=True)

            # Build the WHERE clause next

            where = relations.query.Query()
            self.record_retrieve(model._record, where, values)

            query = f"UPDATE {self.table(model)} SET {relations.sql.assign_clause(clause)} {where.get()}"

            cursor.execute(query, values)

            updated = cursor.rowcount

        elif model._id:

            store = model._fields._names[model._id].store

            for updating in model._each("update"):

                clause = []
                values = []

                self.record_update(updating._record, clause, values)

                values.append(updating[model._id])

                query = f"UPDATE {self.table(model)} SET {relations.sql.assign_clause(clause)} WHERE `{store}`=?"

                cursor.execute(query, values)

                for parent_child in updating.CHILDREN:
                    if updating._children.get(parent_child):
                        updating._children[parent_child].create().update()

                updated += cursor.rowcount

        else:

            raise relations.ModelError(model, "nothing to update from")

        return updated

    def model_delete(self, model):
        """
        Executes the delete
        """

        cursor = self.connection.cursor()

        if model._action == "retrieve":

            where = relations.query.Query()
            values = []
            self.record_retrieve(model._record, where, values)

            query = f"DELETE FROM {self.table(model)} {where.get()}"

        elif model._id:

            store = model._fields._names[model._id].store
            values = []

            for deleting in model._each():
                values.append(deleting[model._id])

            query = f"DELETE FROM {self.table(model)} WHERE `{store}` IN ({','.join(['?'] * len(values))})"

        else:

            raise relations.ModelError(model, "nothing to delete from")

        cursor.execute(query, values)

        return cursor.rowcount
