import unittest
import unittest.mock

import os
import shutil
import copy
import json

import sqlite3

import ipaddress

import relations
import relations_sqlite3

class SourceModel(relations.Model):
    SOURCE = "SQLite3Source"

class Simple(SourceModel):
    id = int
    name = str

class Plain(SourceModel):
    ID = None
    simple_id = int
    name = str

relations.OneToMany(Simple, Plain)

class Meta(SourceModel):
    id = int
    name = str
    flag = bool
    spend = float
    stuff = list
    things = dict, {"extract": "for__0___1"}
    push = str, {"inject": "stuff__-1__relations.io___1"}

def subnet_attr(values, value):

    values["address"] = str(value)
    min_ip = value[0]
    max_ip = value[-1]
    values["min_address"] = str(min_ip)
    values["min_value"] = int(min_ip)
    values["max_address"] = str(max_ip)
    values["max_value"] = int(max_ip)

class Net(SourceModel):

    id = int
    ip = ipaddress.IPv4Address, {
        "attr": {"compressed": "address", "__int__": "value"},
        "init": "address",
        "label": "address",
        "extract": {"address": str, "value": int}
    }
    subnet = ipaddress.IPv4Network, {
        "attr": subnet_attr,
        "init": "address",
        "label": "address"
    }

    LABEL = "ip__address"
    INDEX = "ip__value"

class Unit(SourceModel):
    id = int
    name = str, {"format": "fancy"}

class Test(SourceModel):
    id = int
    unit_id = int
    name = str, {"format": "shmancy"}

class Case(SourceModel):
    id = int
    test_id = int
    name = str

relations.OneToMany(Unit, Test)
relations.OneToOne(Test, Case)

class TestSource(unittest.TestCase):

    maxDiff = None

    def setUp(self):

        self.source = relations_sqlite3.Source("SQLite3Source", "/test_source.db")

        shutil.rmtree("ddl", ignore_errors=True)
        os.makedirs("ddl", exist_ok=True)

    def tearDown(self):

        self.source.connection.close()

        if os.path.exists("/test_source.db"):
            os.remove("/test_source.db")

        if os.path.exists("/private.db"):
            os.remove("/private.db")

    @unittest.mock.patch("relations.SOURCES", {})
    @unittest.mock.patch("sqlite3.connect", unittest.mock.MagicMock())
    def test___init__(self):

        connection = unittest.mock.MagicMock()

        source = relations_sqlite3.Source("unit", "init", connection=connection)
        self.assertFalse(source.created)
        self.assertEqual(source.name, "unit")
        self.assertEqual(source.database, "init")
        self.assertEqual(source.connection, connection)
        self.assertEqual(source.connection.row_factory, sqlite3.Row)
        self.assertEqual(relations.SOURCES["unit"], source)

        source = relations_sqlite3.Source("test", "init.db", schemas={"main": "init", "other": "other.db"}, extra="stuff")
        self.assertTrue(source.created)
        self.assertEqual(source.name, "test")
        self.assertEqual(source.database, "init.db")
        self.assertEqual(source.schemas, {"main": "init", "other": "other.db"})
        self.assertEqual(source.schema, "init")
        self.assertEqual(source.connection, sqlite3.connect.return_value)
        self.assertEqual(source.connection.row_factory, sqlite3.Row)
        self.assertEqual(relations.SOURCES["test"], source)
        sqlite3.connect.assert_called_once_with("init.db", extra="stuff")

    @unittest.mock.patch("relations.SOURCES", {})
    @unittest.mock.patch("sqlite3.connect", unittest.mock.MagicMock())
    def test___del__(self):

        source = relations_sqlite3.Source("test", "init", host="db.com", extra="stuff")
        source.connection = None
        del relations.SOURCES["test"]
        sqlite3.connect.return_value.close.assert_not_called()

        relations_sqlite3.Source("test", "init", host="db.com", extra="stuff")
        del relations.SOURCES["test"]
        sqlite3.connect.return_value.close.assert_called_once_with()

    def test_table_names(self):

        model = {
            "table": "people"
        }
        self.assertEqual(self.source.table_names(model), ("people", []))

        self.source.schema = "public"
        self.assertEqual(self.source.table_names(model), ("people", ["`main`"]))

        model["schema"] = "things"
        self.assertEqual(self.source.table_names(model), ("people", ["`things`"]))

        self.source.schema = "things"
        self.assertEqual(self.source.table_names(model), ("people", ["`main`"]))

        model = unittest.mock.MagicMock()
        model.SCHEMA = None
        self.source.schema = None

        self.source.schema = "public"
        model.TABLE = "people"
        self.assertEqual(self.source.table_names(model), ("people", ["`main`"]))

        model.SCHEMA = "things"
        self.assertEqual(self.source.table_names(model), ("people", ["`things`"]))

        self.source.schema = "things"
        self.assertEqual(self.source.table_names(model), ("people", ["`main`"]))

    def test_table(self):

        model = {
            "table": "people"
        }
        self.assertEqual(self.source.table(model), "`people`")

        self.source.schema = "public"
        self.assertEqual(self.source.table(model), "`main`.`people`")

        model["schema"] = "things"
        self.assertEqual(self.source.table(model), "`things`.`people`")

        model = unittest.mock.MagicMock()
        model.SCHEMA = None

        self.source.schema = "public"
        model.TABLE = "people"
        self.assertEqual(self.source.table(model), "`main`.`people`")

        model.SCHEMA = "things"
        self.assertEqual(self.source.table(model), "`things`.`people`")

        self.assertEqual(self.source.table(model, full=False), "`people`")

    def test_index(self):

        model = {
            "table": "people"
        }
        self.assertEqual(self.source.index(model, "be-cray"), "`people_be_cray`")

        self.source.schema = "public"
        self.assertEqual(self.source.index(model, "be-cray"), "`main`.`people_be_cray`")

        model["schema"] = "things"
        self.assertEqual(self.source.index(model, "be-cray"), "`things`.`people_be_cray`")

        model = unittest.mock.MagicMock()
        model.SCHEMA = None

        self.source.schema = "public"
        model.TABLE = "people"
        self.assertEqual(self.source.index(model, "be-cray"), "`main`.`people_be_cray`")

        model.SCHEMA = "things"
        self.assertEqual(self.source.index(model, "be-cray"), "`things`.`people_be_cray`")

    def test_encode(self):

        model = unittest.mock.MagicMock()
        people = unittest.mock.MagicMock()
        stuff = unittest.mock.MagicMock()
        things = unittest.mock.MagicMock()
        nope = unittest.mock.MagicMock()
        nah = unittest.mock.MagicMock()

        people.kind = str
        stuff.kind = list
        things.kind = dict

        people.auto = False
        stuff.auto = False
        things.auto = False
        nope.auto = True
        nah.auto = False

        people.inject = False
        stuff.inject = False
        things.inject = False
        nope.inject = False
        nah.inject = True

        people.store = "people"
        stuff.store = "stuff"
        things.store = "things"
        nope.store = "nope"

        model._fields._order = [people, stuff, things]

        values = {
            "people": "sure",
            "stuff": None,
            "things": None,
            "nope": False
        }

        self.assertEqual(self.source.encode(model, values), [
            "sure",
            None,
            None
        ])

        values = {
            "people": "sure",
            "stuff": [],
            "things": {},
            "nope": False
        }

        self.assertEqual(self.source.encode(model, values), [
            "sure",
            '[]',
            '{}'
        ])

    def test_decode(self):

        model = unittest.mock.MagicMock()
        people = unittest.mock.MagicMock()
        stuff = unittest.mock.MagicMock()
        things = unittest.mock.MagicMock()

        people.kind = str
        stuff.kind = list
        things.kind = dict

        people.store = "people"
        stuff.store = "stuff"
        things.store = "things"

        model._fields._order = [people, stuff, things]

        values = {
            "people": "sure",
            "stuff": None,
            "things": None
        }

        self.assertEqual(self.source.decode(model, values), {
            "people": "sure",
            "stuff": None,
            "things": None
        })

        values = {
            "people": "sure",
            "stuff": '[]',
            "things": '{}'
        }

        self.assertEqual(self.source.decode(model, values), {
            "people": "sure",
            "stuff": [],
            "things": {}
        })

    def test_walk(self):

        self.assertEqual(self.source.walk("a__b__0___1"), '$.a.b[0]."1"')

    def test_field_init(self):

        class Field:
            pass

        field = Field()

        self.source.field_init(field)

        self.assertIsNone(field.primary_key)
        self.assertIsNone(field.definition)

    def test_model_init(self):

        class Check(relations.Model):
            id = int
            name = str

        model = Check()

        self.source.model_init(model)

        self.assertIn("QUERY", model.UNDEFINE)
        self.assertIsNone(model.SCHEMA)
        self.assertEqual(model.TABLE, "check")
        self.assertEqual(model.QUERY.get(), "SELECT * FROM `check`")
        self.assertIsNone(model.DEFINITION)
        self.assertTrue(model._fields._names["id"].primary_key)
        self.assertTrue(model._fields._names["id"].auto)

    def test_column_define(self):

        # Specific

        field = relations.Field(int, definition="id")
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "id")

        # INTEGER (bool)

        field = relations.Field(bool, store="_flag")
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`_flag` INTEGER")

        # INTEGER (bool) default

        field = relations.Field(bool, store="_flag", default=False)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`_flag` INTEGER NOT NULL DEFAULT 0")

        # INTEGER (bool) none

        field = relations.Field(bool, store="_flag", none=False)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`_flag` INTEGER NOT NULL")

        # INTEGER

        field = relations.Field(int, store="_id")
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`_id` INTEGER")

        # INTEGER default

        field = relations.Field(int, store="_id", default=0)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`_id` INTEGER NOT NULL DEFAULT 0")

        # INTEGER none

        field = relations.Field(int, store="_id", none=False)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`_id` INTEGER NOT NULL")

        # INTEGER primary_key

        field = relations.Field(int, store="_id", primary_key=True)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`_id` INTEGER PRIMARY KEY")

        # INTEGER full

        field = relations.Field(int, store="_id", none=False, primary_key=True, default=0)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`_id` INTEGER NOT NULL PRIMARY KEY DEFAULT 0")

        # REAL

        field = relations.Field(float, store="spend")
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`spend` REAL")

        # REAL default

        field = relations.Field(float, store="spend", default=0.1)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`spend` REAL NOT NULL DEFAULT 0.1")

        # REAL none

        field = relations.Field(float, store="spend", none=False)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`spend` REAL NOT NULL")

        # TEXT

        field = relations.Field(str, name="name")
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`name` TEXT")

        # TEXT length

        field = relations.Field(str, name="name", length=32)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`name` TEXT")

        # TEXT default

        field = relations.Field(str, name="name", default='ya')
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`name` TEXT NOT NULL DEFAULT 'ya'")

        # TEXT none

        field = relations.Field(str, name="name", none=False)
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`name` TEXT NOT NULL")

        # TEXT full

        field = relations.Field(str, name="name", length=32, none=False, default='ya')
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), "`name` TEXT NOT NULL DEFAULT 'ya'")

        # TEXT (list)

        field = relations.Field(list, name='stuff')
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), '`stuff` TEXT NOT NULL')

        # TEXT (dict)

        field = relations.Field(dict, name='things')
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), '`things` TEXT NOT NULL')

        # TEXT (anything)

        field = relations.Field(ipaddress.IPv4Address, name='ip', attr="whatev")
        self.source.field_init(field)
        self.assertEqual(self.source.column_define(field.define()), '`ip` TEXT')

    def test_extract_define(self):

        self.assertEqual(
            self.source.extract_define('grab', 'a__b__0___1', 'bool'),
            "`grab__a__b__0___1` INTEGER AS (json_extract(`grab`,'$.a.b[0].\"1\"'))"
        )
        self.assertEqual(
            self.source.extract_define('grab', 'c__b__0___1', 'int'),
            "`grab__c__b__0___1` INTEGER AS (json_extract(`grab`,'$.c.b[0].\"1\"'))"
        )
        self.assertEqual(
            self.source.extract_define('grab', 'c__d__0___1', 'float'),
            "`grab__c__d__0___1` REAL AS (json_extract(`grab`,'$.c.d[0].\"1\"'))"
        )
        self.assertEqual(
            self.source.extract_define('grab', 'c__d__1___1', 'str'),
            "`grab__c__d__1___1` TEXT AS (json_extract(`grab`,'$.c.d[1].\"1\"'))"
        )
        self.assertEqual(
            self.source.extract_define('grab', 'c__d__1___2', 'dict'),
            "`grab__c__d__1___2` TEXT AS (json_extract(`grab`,'$.c.d[1].\"2\"'))"
        )

    def test_field_define(self):

        # EXTRACTED

        field = relations.Field(dict, name='grab', extract={
            "a__b__0___1": bool,
            "c__b__0___1": int,
            "c__d__0___1": float,
            "c__d__1___1": str,
            "c__d__1___2": list
        })
        self.source.field_init(field)
        definitions = []
        self.source.field_define(field.define(), definitions)
        self.assertEqual(definitions, [
            "`grab` TEXT NOT NULL",
            "`grab__a__b__0___1` INTEGER AS (json_extract(`grab`,'$.a.b[0].\"1\"'))",
            "`grab__c__b__0___1` INTEGER AS (json_extract(`grab`,'$.c.b[0].\"1\"'))",
            "`grab__c__d__0___1` REAL AS (json_extract(`grab`,'$.c.d[0].\"1\"'))",
            "`grab__c__d__1___1` TEXT AS (json_extract(`grab`,'$.c.d[1].\"1\"'))",
            "`grab__c__d__1___2` TEXT AS (json_extract(`grab`,'$.c.d[1].\"2\"'))"
        ])

        # INJECTED

        field = relations.Field(str, name='grab', inject="things__a__b__0___1")
        self.source.field_init(field)
        definitions = []
        self.source.field_define(field.define(), definitions)
        self.assertEqual(definitions, [])

    def test_index_define(self):

        self.assertEqual(
            self.source.index_define(Simple.thy().define(), "special", ["name", "rank"], unique=True),
            "CREATE UNIQUE INDEX `simple_special` ON `simple` (`name`,`rank`)"
        )

        self.assertEqual(
            self.source.index_define(Simple.thy().define(), "special", ["name", "rank"]),
            "CREATE INDEX `simple_special` ON `simple` (`name`,`rank`)"
        )

    def test_model_define(self):

        class Simple(relations.Model):

            SOURCE = "SQLite3Source"
            DEFINITION = "whatever"

            id = int
            name = str

            INDEX = "id"

        self.assertEqual(self.source.model_define(Simple.thy().define()), ["whatever"])

        Simple.DEFINITION = None
        self.assertEqual(self.source.model_define(Simple.thy().define()), [
            """CREATE TABLE IF NOT EXISTS `simple` (
  `id` INTEGER PRIMARY KEY,
  `name` TEXT NOT NULL
)""",
            """CREATE UNIQUE INDEX `simple_name` ON `simple` (`name`)""",
            """CREATE INDEX `simple_id` ON `simple` (`id`)"""
        ])

        cursor = self.source.connection.cursor()
        [cursor.execute(statement) for statement in Simple.define()]
        cursor.close()

    def test_field_add(self):

        # EXTRACTED

        field = relations.Field(dict, name='grab', extract={
            "a__b__0___1": bool,
            "c__b__0___1": int,
            "c__d__0___1": float,
            "c__d__1___1": str,
            "c__d__1___2": list
        })
        self.source.field_init(field)
        migrations = []
        self.source.field_add(field.define(), migrations)
        self.assertEqual(migrations, [
            "ADD `grab` TEXT NOT NULL",
            "ADD `grab__a__b__0___1` INTEGER AS (json_extract(`grab`,'$.a.b[0].\"1\"'))",
            "ADD `grab__c__b__0___1` INTEGER AS (json_extract(`grab`,'$.c.b[0].\"1\"'))",
            "ADD `grab__c__d__0___1` REAL AS (json_extract(`grab`,'$.c.d[0].\"1\"'))",
            "ADD `grab__c__d__1___1` TEXT AS (json_extract(`grab`,'$.c.d[1].\"1\"'))",
            "ADD `grab__c__d__1___2` TEXT AS (json_extract(`grab`,'$.c.d[1].\"2\"'))"
        ])

        # INJECTED

        field = relations.Field(str, name='grab', inject="things__a__b__0___1")
        self.source.field_init(field)
        migrations = []
        self.source.field_add(field.define(), migrations)
        self.assertEqual(migrations, [])

    def test_field_remove(self):

        # EXTRACTED

        field = relations.Field(dict, name='grab', extract={
            "a__b__0___1": bool,
            "c__b__0___1": int,
            "c__d__0___1": float,
            "c__d__1___1": str,
            "c__d__1___2": list
        })
        self.source.field_init(field)
        migrations = []
        self.source.field_remove(field.define(), migrations)
        self.assertEqual(migrations, [
            "DROP `grab`",
            "DROP `grab__a__b__0___1`",
            "DROP `grab__c__b__0___1`",
            "DROP `grab__c__d__0___1`",
            "DROP `grab__c__d__1___1`",
            "DROP `grab__c__d__1___2`"
        ])

        # INJECTED

        field = relations.Field(str, name='toss', inject="things__a__b__0___1")
        self.source.field_init(field)
        migrations = []
        self.source.field_remove(field.define(), migrations)
        self.assertEqual(migrations, [])

    def test_model_add(self):

        self.assertEqual(self.source.model_add(Simple.thy().define()), [
            """CREATE TABLE IF NOT EXISTS `simple` (
  `id` INTEGER PRIMARY KEY,
  `name` TEXT NOT NULL
)""",
            """CREATE UNIQUE INDEX `simple_name` ON `simple` (`name`)"""
        ])

        cursor = self.source.connection.cursor()
        cursor.execute(self.source.model_add(Simple.thy().define())[0])
        cursor.close()

    def test_model_remove(self):

        self.assertEqual(self.source.model_remove(Simple.thy().define()), ["""DROP TABLE IF EXISTS `simple`"""])

        cursor = self.source.connection.cursor()
        cursor.execute(self.source.model_add(Simple.thy().define())[0])
        cursor.execute(self.source.model_remove(Simple.thy().define())[0])
        cursor.close()

    def test_model_change(self):

        class Simple(relations.Model):

            SCHEMA = "private"
            SOURCE = "SQLite3Source"

            id = int
            name = str
            fie = int
            foe = int

            UNIQUE = {
                "foe": ["foe"],
                "labels": ["name", "id"]
            }
            INDEX = {
                "speedy": ["id", "name"],
                "fie": ["fie"],
                "name": ["name"]
            }

        migration = {
            "table": "simples",
            "fields": {
                "add": [
                    {
                        "name": "fee",
                        "store": "fee",
                        "kind": "int",
                        "none": True
                    }
                ],
                "remove": ["fie"],
                "change": {
                    "foe": {
                        "name": "fum",
                        "kind": "float"
                    }
                }
            },
            "unique": {
                "add": {
                    "fee": ["fee"]
                },
                "remove": ["foe"],
                "rename": {
                    "labels": "label"
                }
            },
            "index": {
                "add": {
                    "foe-fee": ["foe", "fee"]
                },
                "remove": ["fie"],
                "rename": {
                    "speedy": "speed"
                }
            }
        }

        self.assertEqual(self.source.model_change(Simple.thy().define(), migration), [
            'ALTER TABLE `private`.`simple` ADD `fee` INTEGER',
            "ALTER TABLE `private`.`simple` RENAME TO `_old_simple`",
            "DROP INDEX `private`.`simple_foe`",
            "DROP INDEX `private`.`simple_labels`",
            "DROP INDEX `private`.`simple_fie`",
            "DROP INDEX `private`.`simple_name`",
            "DROP INDEX `private`.`simple_speedy`",
            """CREATE TABLE IF NOT EXISTS `private`.`simples` (
  `id` INTEGER PRIMARY KEY,
  `name` TEXT NOT NULL,
  `foe` REAL,
  `fee` INTEGER
)""",
            "CREATE UNIQUE INDEX `private`.`simples_label` ON `simples` (`name`,`id`)",
            "CREATE INDEX `private`.`simples_name` ON `simples` (`name`)",
            "CREATE INDEX `private`.`simples_speed` ON `simples` (`id`,`name`)",
            "INSERT INTO `private`.`simples` SELECT `fee` AS `fee`,`foe` AS `foe`,`id` AS `id`,`name` AS `name` FROM `private`.`_old_simple`",
            "DROP TABLE `private`.`_old_simple`"
        ])

        cursor = self.source.connection.cursor()
        cursor.execute("ATTACH DATABASE '/private.db' AS `private`")
        [cursor.execute(statement) for statement in self.source.model_define(Simple.thy().define())]
        [cursor.execute(statement) for statement in self.source.model_change(Simple.thy().define(), migration)]
        cursor.close()

    def test_field_create(self):

        # Standard

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        fields = []
        clause = []
        self.source.field_create( field, fields, clause)
        self.assertEqual(fields, ["`id`"])
        self.assertEqual(clause, ["?"])
        self.assertFalse(field.changed)

        # auto

        field = relations.Field(int, name="id", auto=True)
        self.source.field_init(field)
        fields = []
        clause = []
        self.source.field_create( field, fields, clause)
        self.assertEqual(fields, [])
        self.assertEqual(clause, [])

        # inject

        field = relations.Field(int, name="id", inject=True)
        self.source.field_init(field)
        fields = []
        clause = []
        self.source.field_create( field, fields, clause)
        self.assertEqual(fields, [])
        self.assertEqual(clause, [])

    def test_model_create(self):

        simple = Simple("sure")
        simple.plain.add("fine")

        cursor = self.source.connection.cursor()
        [cursor.execute(statement) for statement in Simple.define() + Plain.define() + Meta.define()]

        simple.create()

        self.assertEqual(simple.id, 1)
        self.assertEqual(simple._action, "update")
        self.assertEqual(simple._record._action, "update")
        self.assertEqual(simple.plain[0].simple_id, 1)
        self.assertEqual(simple.plain._action, "update")
        self.assertEqual(simple.plain[0]._record._action, "update")

        cursor.execute("SELECT * FROM simple")
        self.assertEqual(dict(cursor.fetchone()), {"id": 1, "name": "sure"})

        simples = Simple.bulk().add("ya").create()
        self.assertEqual(simples._models, [])

        cursor.execute("SELECT * FROM simple WHERE name='ya'")
        self.assertEqual(dict(cursor.fetchone()), {"id": 2, "name": "ya"})

        cursor.execute("SELECT * FROM plain")
        self.assertEqual(dict(cursor.fetchone()), {"simple_id": 1, "name": "fine"})

        Meta("yep", True, 3.50, [1, None], {"for": [{"1": "yep"}]}, "sure").create()
        cursor.execute("SELECT * FROM meta")
        self.assertEqual(dict(cursor.fetchone()), {
            "id": 1,
            "name": "yep",
            "flag": True,
            "spend": 3.50,
            "stuff": '[1, {"relations.io": {"1": "sure"}}]',
            "things": '{"for": [{"1": "yep"}]}',
            "things__for__0___1": "yep"
        })

        cursor.close()

    def test_field_retrieve(self):

        # IN

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter([1, 2, 3], "in")
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "`id` IN (?,?,?)")
        self.assertEqual(values, [1, 2, 3])

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter([], "in")
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "FALSE")
        self.assertEqual(values, [])

        # NOT IN

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter([1, 2, 3], "ne")
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "`id` NOT IN (?,?,?)")
        self.assertEqual(values, [1, 2, 3])

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter([], "ne")
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "TRUE")
        self.assertEqual(values, [])

        # LIKE

        field = relations.Field(int, name='id')
        self.source.field_init(field)
        field.filter(1, 'like')
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, '`id` LIKE ?')
        self.assertEqual(values, ["%1%"])

        # NOT LIKE

        field = relations.Field(int, name='id')
        self.source.field_init(field)
        field.filter(1, 'notlike')
        query = relations.query.Query()
        values = []
        self.source.field_retrieve(field, query, values)
        self.assertEqual(query.wheres, '`id` NOT LIKE ?')
        self.assertEqual(values, ["%1%"])

        # IS NULL

        field = relations.Field(int, name='id')
        self.source.field_init(field)
        field.filter(True, 'null')
        query = relations.query.Query()
        values = []
        self.source.field_retrieve(field, query, values)
        self.assertEqual(query.wheres, '`id` IS NULL')
        self.assertEqual(values, [])

        # IS NOT NULL

        field = relations.Field(int, name='id')
        self.source.field_init(field)
        field.filter(False, 'null')
        query = relations.query.Query()
        values = []
        self.source.field_retrieve(field, query, values)
        self.assertEqual(query.wheres, '`id` IS NOT NULL')
        self.assertEqual(values, [])

        # JSON

        field = relations.Field(dict, name='meta')
        self.source.field_init(field)
        field.filter(1, 'a__b__0___1')
        query = relations.query.Query()
        values = []
        self.source.field_retrieve(field, query, values)
        self.assertEqual(query.wheres, "json_extract(`meta`,?)=?")
        self.assertEqual(values, ['$.a.b[0]."1"', 1])

        field = relations.Field(dict, name='meta', extract="a__b__0___1")
        self.source.field_init(field)
        field.filter(1, 'a__b__0___1')
        query = relations.query.Query()
        values = []
        self.source.field_retrieve(field, query, values)
        self.assertEqual(query.wheres, "`meta__a__b__0___1`=?")
        self.assertEqual(values, [1])

        # =

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter(1)
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "`id`=?")
        self.assertEqual(values, [1])

        # >

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter(1, "gt")
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "`id`>?")
        self.assertEqual(values, [1])

        # >=

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter(1, "gte")
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "`id`>=?")
        self.assertEqual(values, [1])

        # <

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter(1, "lt")
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "`id`<?")
        self.assertEqual(values, [1])

        # <=

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        field.filter(1, "lte")
        query = relations.query.Query()
        values = []
        self.source.field_retrieve( field, query, values)
        self.assertEqual(query.wheres, "`id`<=?")
        self.assertEqual(values, [1])

    def test_model_like(self):

        cursor = self.source.connection.cursor()

        [cursor.execute(statement) for statement in Unit.define() + Test.define() + Case.define() + Net.define()]

        Unit([["stuff"], ["people"]]).create()

        unit = Unit.one()

        query = copy.deepcopy(unit.QUERY)
        values = []
        self.source.model_like(unit, query, values)
        self.assertEqual(query.wheres, '')
        self.assertEqual(values, [])

        unit = Unit.one(like="p")
        query = copy.deepcopy(unit.QUERY)
        values = []
        self.source.model_like(unit, query, values)
        self.assertEqual(query.wheres, '(`name` LIKE ?)')
        self.assertEqual(values, ['%p%'])

        unit = Unit.one(name="people")
        unit.test.add("things")[0]
        unit.update()

        test = Test.many(like="p")
        query = copy.deepcopy(test.QUERY)
        values = []
        self.source.model_like(test, query, values)
        self.assertEqual(query.wheres, '(`unit_id` IN (?) OR `name` LIKE ?)')
        self.assertEqual(values, [unit.id, '%p%'])
        self.assertFalse(test.overflow)

        test = Test.many(like="p", _chunk=1)
        query = copy.deepcopy(test.QUERY)
        values = []
        self.source.model_like(test, query, values)
        self.assertEqual(query.wheres, '(`unit_id` IN (?) OR `name` LIKE ?)')
        self.assertEqual(values, [unit.id, '%p%'])
        self.assertTrue(test.overflow)

        Unit.many().delete()
        test = Test.many(like="p", _chunk=1)
        query = copy.deepcopy(test.QUERY)
        values = []
        self.source.model_like(test, query, values)
        self.assertEqual(query.wheres, '(`name` LIKE ?)')
        self.assertEqual(values, ['%p%'])

        class Nut(SourceModel):

            id = int
            name = str
            ip = ipaddress.IPv4Address, {"attr": {"compressed": "address", "__int__": "value"}, "init": "address", "label": ["address", "value"], "extract": "address"}
            subnet = ipaddress.IPv4Network, {"attr": subnet_attr, "init": "address", "label": "address"}

            LABEL = ["ip", "subnet__min_address"]
            UNIQUE = False

        net = Nut.many(like="p")
        query = copy.deepcopy(net.QUERY)
        values = []
        self.source.model_like(net, query, values)
        self.assertEqual(query.wheres, '(`ip__address` LIKE ? OR json_extract(`ip`,?) LIKE ? OR json_extract(`subnet`,?) LIKE ?)')
        self.assertEqual(values, ['%p%', '$.value', '%p%', '$.min_address', '%p%'])

    def test_model_sort(self):

        unit = Unit.one()

        query = copy.deepcopy(unit.QUERY)
        self.source.model_sort(unit, query)
        self.assertEqual(query.order_bys, '`name`')

        unit._sort = ['-id']
        query = copy.deepcopy(unit.QUERY)
        self.source.model_sort(unit, query)
        self.assertEqual(query.order_bys, '`id` DESC')
        self.assertIsNone(unit._sort)

    def test_model_limit(self):

        unit = Unit.one()

        query = copy.deepcopy(unit.QUERY)
        values = []
        self.source.model_limit(unit, query, values)
        self.assertEqual(query.limits, '')
        self.assertEqual(values, [])

        unit._limit = 2
        query = copy.deepcopy(unit.QUERY)
        values = []
        self.source.model_limit(unit, query, values)
        self.assertEqual(query.limits, '?')
        self.assertEqual(values, [2])

        unit._offset = 1
        query = copy.deepcopy(unit.QUERY)
        values = []
        self.source.model_limit(unit, query, values)
        self.assertEqual(query.limits, '? OFFSET ?')
        self.assertEqual(values, [2, 1])

    def test_model_count(self):

        cursor = self.source.connection.cursor()

        [cursor.execute(statement) for statement in Unit.define() + Test.define() + Case.define()]

        Unit([["stuff"], ["people"]]).create()

        self.assertEqual(Unit.many().count(), 2)

        self.assertEqual(Unit.many(name="people").count(), 1)

        self.assertEqual(Unit.many(like="p").count(), 1)

    def test_model_retrieve(self):

        cursor = self.source.connection.cursor()

        [cursor.execute(statement) for statement in Unit.define() + Test.define() + Case.define() + Meta.define() + Net.define()]

        Unit([["stuff"], ["people"]]).create()

        models = Unit.one(name__in=["people", "stuff"])
        self.assertRaisesRegex(relations.ModelError, "unit: more than one retrieved", models.retrieve)

        model = Unit.one(name="things")
        self.assertRaisesRegex(relations.ModelError, "unit: none retrieved", model.retrieve)

        self.assertIsNone(model.retrieve(False))

        unit = Unit.one(name="people")

        self.assertEqual(unit.id, 2)
        self.assertEqual(unit._action, "update")
        self.assertEqual(unit._record._action, "update")

        unit.test.add("things")[0].case.add("persons")
        unit.update()

        model = Unit.many(test__name="things")

        self.assertEqual(model.id, [2])
        self.assertEqual(model[0]._action, "update")
        self.assertEqual(model[0]._record._action, "update")
        self.assertEqual(model[0].test[0].id, 1)
        self.assertEqual(model[0].test[0].case.name, "persons")

        model = Unit.many(like="p")
        self.assertEqual(model.name, ["people"])

        model = Test.many(like="p").retrieve()
        self.assertEqual(model.name, ["things"])
        self.assertFalse(model.overflow)

        model = Test.many(like="p", _chunk=1).retrieve()
        self.assertEqual(model.name, ["things"])
        self.assertTrue(model.overflow)

        Meta("yep", True, 1.1, [1, None], {"a": 1}).create()
        model = Meta.one(name="yep")

        self.assertEqual(model.flag, True)
        self.assertEqual(model.spend, 1.1)
        self.assertEqual(model.stuff, [1, {"relations.io": {"1": None}}])
        self.assertEqual(model.things, {"a": 1})

        self.assertEqual(Unit.many().name, ["people", "stuff"])
        self.assertEqual(Unit.many().sort("-name").name, ["stuff", "people"])
        self.assertEqual(Unit.many().sort("-name").limit(1, 1).name, ["people"])
        self.assertEqual(Unit.many().sort("-name").limit(0).name, [])
        self.assertEqual(Unit.many(name="people").limit(1).name, ["people"])

        Meta("dive", stuff=[1, 2, 3, None], things={"a": {"b": [1], "c": "sure"}, "4": 5, "for": [{"1": "yep"}]}).create()

        model = Meta.many(stuff__1=2)
        self.assertEqual(model[0].name, "dive")

        model = Meta.many(things__a__b__0=1)
        self.assertEqual(model[0].name, "dive")

        model = Meta.many(things__a__c__like="su")
        self.assertEqual(model[0].name, "dive")

        model = Meta.many(things__a__d__null=True)
        self.assertEqual(model[0].name, "dive")

        model = Meta.many(things___4=5)
        self.assertEqual(model[0].name, "dive")

        model = Meta.many(things__a__b__0__gt=1)
        self.assertEqual(len(model), 0)

        model = Meta.many(things__a__c__notlike="su")
        self.assertEqual(len(model), 0)

        model = Meta.many(things__a__d__null=False)
        self.assertEqual(len(model), 0)

        model = Meta.many(things___4=6)
        self.assertEqual(len(model), 0)

        Net(ip="1.2.3.4", subnet="1.2.3.0/24").create()
        Net().create()

        model = Net.many(like='1.2.3.')
        self.assertEqual(model[0].ip.compressed, "1.2.3.4")

        model = Net.many(ip__address__like='1.2.3.')
        self.assertEqual(model[0].ip.compressed, "1.2.3.4")

        model = Net.many(ip__value__gt=int(ipaddress.IPv4Address('1.2.3.0')))
        self.assertEqual(model[0].ip.compressed, "1.2.3.4")

        model = Net.many(subnet__address__like='1.2.3.')
        self.assertEqual(model[0].ip.compressed, "1.2.3.4")

        model = Net.many(subnet__min_value=int(ipaddress.IPv4Address('1.2.3.0')))
        self.assertEqual(model[0].ip.compressed, "1.2.3.4")

        model = Net.many(ip__address__notlike='1.2.3.')
        self.assertEqual(len(model), 0)

        model = Net.many(ip__value__lt=int(ipaddress.IPv4Address('1.2.3.0')))
        self.assertEqual(len(model), 0)

        model = Net.many(subnet__address__notlike='1.2.3.')
        self.assertEqual(len(model), 0)

        model = Net.many(subnet__max_value=int(ipaddress.IPv4Address('1.2.3.0')))
        self.assertEqual(len(model), 0)

    def test_model_labels(self):

        cursor = self.source.connection.cursor()

        [cursor.execute(statement) for statement in Unit.define() + Test.define() + Case.define() + Net.define()]

        Unit("people").create().test.add("stuff").add("things").create()

        labels = Unit.many().labels()

        self.assertEqual(labels.id, "id")
        self.assertEqual(labels.label, ["name"])
        self.assertEqual(labels.parents, {})
        self.assertEqual(labels.format, ["fancy"])

        self.assertEqual(labels.ids, [1])
        self.assertEqual(labels.labels,{1: ["people"]})

        labels = Test.many().labels()

        self.assertEqual(labels.id, "id")
        self.assertEqual(labels.label, ["unit_id", "name"])

        self.assertEqual(labels.parents["unit_id"].id, "id")
        self.assertEqual(labels.parents["unit_id"].label, ["name"])
        self.assertEqual(labels.parents["unit_id"].parents, {})
        self.assertEqual(labels.parents["unit_id"].format, ["fancy"])

        self.assertEqual(labels.format, ["fancy", "shmancy"])

        self.assertEqual(labels.ids, [1, 2])
        self.assertEqual(labels.labels, {
            1: ["people", "stuff"],
            2: ["people", "things"]
        })

        Net(ip="1.2.3.4", subnet="1.2.3.0/24").create()

        self.assertEqual(Net.many().labels().labels, {
            1: ["1.2.3.4"]
        })

    def test_field_update(self):

        # Standard

        field = relations.Field(int, name="id")
        self.source.field_init(field)
        clause = []
        values = []
        self.source.field_update(field, {"id": 1}, clause, values)
        self.assertEqual(clause, ['`id`=?'])
        self.assertEqual(values, [1])

        # Non standard

        field = relations.Field(dict, name="id")
        self.source.field_init(field)
        clause = []
        values = []
        self.source.field_update(field, {"id": {"a": 1}}, clause, values)
        self.assertEqual(clause, ['`id`=?'])
        self.assertEqual(values, ['{"a": 1}'])

        # Non existent

        field = relations.Field(dict, name="id")
        self.source.field_init(field)
        clause = []
        values = []
        self.source.field_update(field, {}, clause, values)
        self.assertEqual(clause, [])
        self.assertEqual(values, [])

    def test_model_update(self):

        cursor = self.source.connection.cursor()

        [cursor.execute(statement) for statement in Unit.define() + Test.define() + Case.define() + Meta.define() + Net.define()]

        Unit([["people"], ["stuff"]]).create()

        unit = Unit.many(id=2).set(name="things")

        self.assertEqual(unit.update(), 1)

        unit = Unit.one(2)

        unit.name = "thing"
        unit.test.add("moar")

        self.assertEqual(unit.update(), 1)
        self.assertEqual(unit.name, "thing")
        self.assertEqual(unit.test[0].id, 1)
        self.assertEqual(unit.test[0].name, "moar")

        Meta("yep", True, 1.1, [1, None], {"a": 1}).create()
        Meta.one(name="yep").set(flag=False, stuff=[], things={}).update()

        model = Meta.one(name="yep")
        self.assertEqual(model.flag, False)
        self.assertEqual(model.spend, 1.1)
        self.assertEqual(model.stuff, [])
        self.assertEqual(model.things, {})

        plain = Plain.one()
        self.assertRaisesRegex(relations.ModelError, "plain: nothing to update from", plain.update)

        ping = Net(ip="1.2.3.4", subnet="1.2.3.0/24").create()
        pong = Net(ip="5.6.7.8", subnet="5.6.7.0/24").create()

        Net.many().set(subnet="9.10.11.0/24").update()

        self.assertEqual(Net.one(ping.id).subnet.compressed, "9.10.11.0/24")
        self.assertEqual(Net.one(pong.id).subnet.compressed, "9.10.11.0/24")

        Net.one(ping.id).set(ip="13.14.15.16").update()
        self.assertEqual(Net.one(ping.id).ip.compressed, "13.14.15.16")
        self.assertEqual(Net.one(pong.id).ip.compressed, "5.6.7.8")

    def test_model_delete(self):

        cursor = self.source.connection.cursor()

        [cursor.execute(statement) for statement in Unit.define() + Test.define() + Case.define()]

        unit = Unit("people")
        unit.test.add("stuff").add("things")
        unit.create()

        self.assertEqual(Test.one(id=2).delete(), 1)
        self.assertEqual(len(Test.many()), 1)

        self.assertEqual(Unit.one(1).test.delete(), 1)
        self.assertEqual(Unit.one(1).retrieve().delete(), 1)
        self.assertEqual(len(Unit.many()), 0)
        self.assertEqual(len(Test.many()), 0)

        self.assertEqual(Test.many().delete(), 0)

        [cursor.execute(statement) for statement in Plain.define()]

        plain = Plain(0, "nope").create()
        self.assertRaisesRegex(relations.ModelError, "plain: nothing to delete from", plain.delete)

    def test_definition_convert(self):

        with open("ddl/general.json", 'w') as ddl_file:
            json.dump({
                "simple": Simple.thy().define(),
                "plain": Plain.thy().define()
            }, ddl_file)

        os.makedirs("ddl/sourced", exist_ok=True)

        self.source.definition_convert("ddl/general.json", "ddl/sourced")

        with open("ddl/sourced/general.sql", 'r') as ddl_file:
            self.assertEqual(ddl_file.read(), """CREATE TABLE IF NOT EXISTS `plain` (
  `simple_id` INTEGER,
  `name` TEXT NOT NULL
);

CREATE UNIQUE INDEX `plain_simple_id_name` ON `plain` (`simple_id`,`name`);

CREATE TABLE IF NOT EXISTS `simple` (
  `id` INTEGER PRIMARY KEY,
  `name` TEXT NOT NULL
);

CREATE UNIQUE INDEX `simple_name` ON `simple` (`name`);
""")

    def test_migration_convert(self):

        with open("ddl/general.json", 'w') as ddl_file:
            json.dump({
                "add": {"simple": Simple.thy().define()},
                "remove": {"simple": Simple.thy().define()},
                "change": {
                    "simple": {
                        "definition": Simple.thy().define(),
                        "migration": {
                            "source": "PyMySQLSource",
                            "table": "simples"
                        }
                    }
                }
            }, ddl_file)

        os.makedirs("ddl/sourced", exist_ok=True)

        self.source.migration_convert("ddl/general.json", "ddl/sourced")

        with open("ddl/sourced/general.sql", 'r') as ddl_file:
            self.assertEqual(ddl_file.read(), """CREATE TABLE IF NOT EXISTS `simple` (
  `id` INTEGER PRIMARY KEY,
  `name` TEXT NOT NULL
);

CREATE UNIQUE INDEX `simple_name` ON `simple` (`name`);

DROP TABLE IF EXISTS `simple`;

ALTER TABLE `simple` RENAME TO `_old_simple`;

DROP INDEX `simple_name`;

CREATE TABLE IF NOT EXISTS `simples` (
  `id` INTEGER PRIMARY KEY,
  `name` TEXT NOT NULL
);

CREATE UNIQUE INDEX `simples_name` ON `simples` (`name`);

INSERT INTO `simples` SELECT `id` AS `id`,`name` AS `name` FROM `_old_simple`;

DROP TABLE `_old_simple`;
""")

    def test_execute(self):

        self.source.execute("")

        self.source.execute("""CREATE TABLE IF NOT EXISTS `simple` (
  `id` INTEGER PRIMARY KEY,
  `name` TEXT NOT NULL
)""")

        cursor = self.source.connection.cursor()

        cursor.execute("SELECT * FROM pragma_table_info('simple')")

        id = cursor.fetchone()
        self.assertEqual(id["name"], "id")
        self.assertEqual(id["type"], "INTEGER")

        name = cursor.fetchone()
        self.assertEqual(name["name"], "name")
        self.assertEqual(name["type"], "TEXT")

    def test_migrate(self):

        migrations = relations.Migrations()

        migrations.generate([Unit])
        migrations.generate([Unit, Test])
        migrations.convert(self.source.name)

        self.assertTrue(self.source.migrate(f"ddl/{self.source.name}/{self.source.KIND}"))

        self.assertEqual(Unit.many().count(), 0)
        self.assertEqual(Test.many().count(), 0)

        self.assertFalse(self.source.migrate(f"ddl/{self.source.name}/{self.source.KIND}"))

        migrations.generate([Unit, Test, Case])
        migrations.convert(self.source.name)

        self.assertTrue(self.source.migrate(f"ddl/{self.source.name}/{self.source.KIND}"))

        self.assertEqual(Case.many().count(), 0)

        self.assertFalse(self.source.migrate(f"ddl/{self.source.name}/{self.source.KIND}"))
