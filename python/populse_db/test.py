from datetime import datetime, date, time
import os
import shutil
import tempfile
import unittest

from populse_db import Database
from populse_db.database import check_value_type
from populse_db.filter import literal_parser, FilterToSQL


class TestsSQLiteInMemory(unittest.TestCase):
    def test_add_get_document(self):
        now = datetime.now()
        db = Database('sqlite://:memory:')
        with db as dbs:
            dbs.add_collection('test', 'index')
            base_doc = {
                'string': 'string',
                'int': 1,
                'float': 1.4,
                'boolean': True,
                'datetime': now,
                'date': now.date(),
                'time': now.time(),
                'dict': {
                    'string': 'string',
                    'int': 1,
                    'float': 1.4,
                    'boolean': True,
                }
            }
            doc = base_doc.copy()
            for k, v in base_doc.items():
                lk = 'list_%s' % k
                doc[lk] = [v]
            doc['index'] = 'test'
            dbs.add_document('test', doc)
            stored_doc = dbs.get_document('test', 'test')
            self.maxDiff = None
            self.assertEqual(doc, stored_doc)

def create_test_case(**database_creation_parameters):
    class TestDatabaseMethods(unittest.TestCase):
        """
        Class executing the unit tests of populse_db
        """

        def setUp(self):
            """
            Called before every unit test
            Creates a temporary folder containing the database file that will be used for the test
            """
            self.database_creation_parameters = dict(database_creation_parameters)
            if 'database_url' not in self.database_creation_parameters:
                self.temp_folder = tempfile.mkdtemp(prefix='populse_db')
                path = os.path.join(self.temp_folder, "test.db")
                self.database_creation_parameters['database_url'] = 'sqlite:///' + path
            else:
                self.temp_folder = None
            self.database_url = self.database_creation_parameters['database_url']

        def tearDown(self):
            """
            Called after every unit test
            Deletes the temporary folder created for the test
            """
            if self.temp_folder:
                shutil.rmtree(self.temp_folder)
                del self.database_creation_parameters['database_url']
            self.temp_folder = None
            
        def create_database(self, clear=True):
            """
            Opens the database
            :param clear: Bool to know if the database must be cleared
            """

            try:
                db = Database(**self.database_creation_parameters)
            except Exception as e:
                if self.database_creation_parameters['database_url'].startswith('postgresql'):
                    raise unittest.SkipTest(str(e))
                raise
            except ImportError as e:
                if ('psycopg2' in str(e) and 
                    self.database_creation_parameters['database_url'].startswith('postgresql')):
                    raise unittest.SkipTest(str(e))
                raise
            if clear:
                with db as dbs:
                    dbs.clear()
            return db

        def test_wrong_constructor_parameters(self):
            """
            Tests the parameters of the Database class constructor
            """
            # Testing with wrong engine
            self.assertRaises(ValueError, lambda : Database("engine").__enter__())

        def test_add_field(self):
            """
            Tests the method adding a field
            """

            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("collection1", "name")

                # Testing with a first field
                session.add_field("collection1", "PatientName", str,
                                  description="Name of the patient")

                # Checking the field properties
                field = session.get_field("collection1", "PatientName")
                self.assertEqual(field["name"], "PatientName")
                self.assertEqual(field["type"],str)
                self.assertEqual(field["description"], "Name of the patient")
                self.assertEqual(field["collection"], "collection1")

                # Testing with a field that already exists
                self.assertRaises(Exception, lambda : session.add_field("collection1", "PatientName", str,
                                      "Name of the patient"))

                # Testing with several field types
                session.add_field("collection1", "BandWidth", float, None)
                session.add_field("collection1", "AcquisitionTime", time, None)
                session.add_field("collection1", "AcquisitionDate", datetime, None)
                session.add_field("collection1", "Dataset dimensions", list[int],
                                  None)
                session.add_field("collection1", "Boolean", bool, None)
                session.add_field("collection1", "Boolean list", list[bool], None)

                # Testing with close field names
                session.add_field("collection1", "Bits per voxel", int, "with space")
                session.add_field("collection1", "Bitspervoxel", int,
                                  "without space")
                with self.assertRaises(Exception):
                    session.add_field("collection1", "bitspervoxel", int,
                                    "lower case")
                self.assertEqual(session.get_field(
                    "collection1", "Bitspervoxel")["description"], "without space")
                self.assertEqual(session.get_field(
                    "collection1", "Bits per voxel")["description"], "with space")
                with self.assertRaises(Exception):
                    self.assertEqual(session.get_field(
                        "collection1", "bitspervoxel")["description"], "lower case")

                # Testing with wrong parameters
                self.assertRaises(ValueError, lambda : session.add_field("collection_not_existing", "Field", list[int],
                                      None))
                self.assertRaises(ValueError, lambda : session.add_field(True, "Field", list[int], None))
                self.assertRaises(Exception, lambda : session.add_field("collection1", "Patient Name", None, None))

                # Testing that the document primary key field is taken
                self.assertRaises(Exception, lambda : session.add_field("collection1", "name", str, None))

                with self.assertRaises(Exception):
                    session.remove_field("collection", "name")

        def test_add_fields(self):
            """
            Tests the method adding several fields
            """

            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("collection1")

                # Adding several fields
                session.add_field("collection1", "First name", str, "")
                session.add_field("collection1", "Last name", str, "")
                collection_fields = list(session.get_fields_names("collection1"))
                self.assertEqual(len(collection_fields), 3)
                self.assertTrue("primary_key" in collection_fields)
                self.assertTrue("First name" in collection_fields)
                self.assertTrue("Last name" in collection_fields)


        def test_remove_field(self):
            """
            Tests the method removing a field
            """

            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("current", "name")

                # Adding fields
                session.add_field("current", "PatientName", str,
                                  "Name of the patient")
                session.add_field("current", "SequenceName", str, None)
                session.add_field("current", "Dataset dimensions", list[int], None)

                # Adding documents
                document = {}
                document["name"] = "document1"
                session.add_document("current", document)
                document = {}
                document["name"] = "document2"
                session.add_document("current", document)

                # Adding values
                session.add_value("current", "document1", "PatientName", "Guerbet")
                session.add_value("current", "document1", "SequenceName", "RARE")
                session.add_value("current", "document1", "Dataset dimensions", [1, 2])

                # Removing fields
                session.remove_field("current", "PatientName")
                session.remove_field("current", "Dataset dimensions")

                # Testing that the field does not exist anymore
                self.assertIsNone(session.get_field("current", "PatientName"))
                self.assertIsNone(session.get_field("current", "Dataset dimensions"))

                # Testing that the field values are removed
                self.assertIsNone(session.get_value("current", "document1", "PatientName"))
                self.assertEqual(session.get_value(
                    "current", "document1", "SequenceName"), "RARE")
                self.assertIsNone(session.get_value(
                    "current", "document1", "Dataset dimensions"))

                # Testing with list of fields
                session.remove_field("current", ["SequenceName"])
                self.assertIsNone(session.get_field("current", "SequenceName"))

                # Adding fields again
                session.add_field("current", "PatientName", str,
                                  "Name of the patient")
                session.add_field("current", "SequenceName", str, None)
                session.add_field("current", "Dataset dimensions", list[int], None)

                # Testing with list of fields
                session.remove_field("current", ["SequenceName", "PatientName"])
                self.assertIsNone(session.get_field("current", "SequenceName"))
                self.assertIsNone(session.get_field("current", "PatientName"))

                # Testing with a field not existing
                self.assertRaises(ValueError, lambda : session.remove_field("not_existing", "document1"))
                self.assertRaises(ValueError, lambda : session.remove_field(1, "NotExisting"))
                self.assertRaises(ValueError, lambda : session.remove_field("current", "NotExisting"))
                self.assertRaises(ValueError, lambda : session.remove_field("current", "Dataset dimension"))
                self.assertRaises(ValueError, lambda : session.remove_field("current", ["SequenceName", "PatientName", "Not_Existing"]))

                # Testing with wrong parameters
                self.assertRaises(Exception, lambda : session.remove_field("current", 1))
                self.assertRaises(Exception, lambda : session.remove_field("current", None))

                # Removing list of fields with list type
                session.add_field("current", "list1", list[int], None)
                session.add_field("current", "list2", list[str], None)
                session.remove_field("current", ["list1", "list2"])
                self.assertIsNone(session.get_field("current", "list1"))
                self.assertIsNone(session.get_field("current", "list2"))

                # TODO Testing column removal

        def test_get_field(self):
            """
            Tests the method giving the field row given a field
            """

            database = self.create_database()
            with database as session:
                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding a field
                session.add_field("collection1", "PatientName", str,
                                  "Name of the patient")

                # Testing that the field is returned if it exists
                self.assertIsNotNone(session.get_field("collection1", "PatientName"))

                # Testing that None is returned if the field does not exist
                self.assertIsNone(session.get_field("collection1", "Test"))

                # Testing that None is returned if the collection does not exist
                self.assertIsNone(session.get_field("collection_not_existing", "PatientName"))

                # Testing that None is returned if both collection and field do not exist
                self.assertIsNone(session.get_field("collection_not_existing", "Test"))

        def test_get_fields(self):
            """
            Tests the method giving all fields rows, given a collection
            """

            database = self.create_database()
            with database as session:
                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding a field
                session.add_field("collection1", "PatientName", str,
                                  "Name of the patient")

                fields = session.get_fields("collection1")
                self.assertEqual(len(fields), 2)

                session.add_field("collection1", "SequenceName", str,
                                  "Name of the patient")

                fields = session.get_fields("collection1")
                self.assertEqual(len(fields), 3)

                # Adding a second collection
                session.add_collection("collection2", "id")

                fields = session.get_fields("collection1")
                self.assertEqual(len(fields), 3)

                # Testing with a collection not existing
                self.assertEqual(session.get_fields("collection_not_existing"), [])

        def test_set_value(self):

            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding a document
                document = {}
                document["name"] = "document1"
                session.add_document("collection1", document)

                # Adding fields
                session.add_field("collection1", "PatientName", str,
                                  "Name of the patient")
                session.add_field(
                    "collection1", "Bits per voxel", int, None)
                session.add_field(
                    "collection1", "bits per voxel", int, None)
                session.add_field(
                    "collection1", "AcquisitionDate", datetime, None)
                session.add_field(
                    "collection1", "AcquisitionTime", time, None)

                # Adding values and setting them
                session.add_value("collection1", "document1", "PatientName", "test", "test")
                session.set_value("collection1", "document1", "PatientName", "test2")

                session.add_value("collection1", "document1", "Bits per voxel", 1, 1)
                session.set_value("collection1", "document1", "Bits per voxel", 2)
                session.set_value("collection1", "document1", "bits per voxel", 42)

                date = datetime(2014, 2, 11, 8, 5, 7)
                session.add_value("collection1", "document1", "AcquisitionDate", date, date)
                self.assertEqual(session.get_value("collection1", "document1", "AcquisitionDate"), date)
                date = datetime(2015, 2, 11, 8, 5, 7)
                session.set_value("collection1", "document1", "AcquisitionDate", date)

                time = datetime(2014, 2, 11, 0, 2, 20).time()
                session.add_value("collection1", "document1", "AcquisitionTime", time, time)
                self.assertEqual(session.get_value(
                    "collection1", "document1", "AcquisitionTime"), time)
                time = datetime(2014, 2, 11, 15, 24, 20).time()
                session.set_value("collection1", "document1", "AcquisitionTime", time)

                # Testing that the values are actually set
                self.assertEqual(session.get_value(
                    "collection1", "document1", "PatientName"), "test2")
                self.assertEqual(session.get_value(
                    "collection1", "document1", "Bits per voxel"), 2)
                self.assertEqual(session.get_value(
                    "collection1", "document1", "bits per voxel"), 42)
                self.assertEqual(session.get_value(
                    "collection1", "document1", "AcquisitionDate"), date)
                self.assertEqual(session.get_value(
                    "collection1", "document1", "AcquisitionTime"), time)
                session.set_value("collection1", "document1", "PatientName", None)
                self.assertIsNone(session.get_value("collection1", "document1", "PatientName"))

                # Testing when the value is not existing
                self.assertRaises(ValueError, lambda : session.set_value("collection_not_existing", "document3", "PatientName", None))
                self.assertRaises(ValueError, lambda : session.set_value("collection1", "document3", "PatientName", None))
                self.assertRaises(ValueError, lambda : session.set_value("collection1", "document1", "NotExisting", None))
                self.assertRaises(ValueError, lambda : session.set_value("collection1", "document3", "NotExisting", None))

                # Testing with wrong types
                self.assertRaises(ValueError, lambda : session.set_value("collection1", "document1", "Bits per voxel", "test"))
                self.assertEqual(session.get_value("collection1",
                                                   "document1", "Bits per voxel"), 2)
                self.assertRaises(ValueError, lambda : session.set_value("collection1", "document1", "Bits per voxel", 35.8))
                self.assertEqual(session.get_value(
                    "collection1", "document1", "Bits per voxel"), 2)

                # Testing with wrong parameters
                self.assertRaises(ValueError, lambda : session.set_value(False, "document1", "Bits per voxel", 35))
                self.assertRaises(ValueError, lambda : session.set_value("collection1", 1, "Bits per voxel", "2"))
                self.assertRaises(ValueError, lambda : session.set_value("collection1", "document1", None, "1"))
                self.assertRaises(ValueError, lambda : session.set_value("collection1", 1, None, True))

                # Testing that setting a primary key value is impossible
                self.assertRaises(ValueError, lambda : session.set_value("collection1", "document1", "name", None))

        def test_set_values(self):
            """
            Tests the method setting several values of a document
            """

            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("collection1")

                # Adding fields
                session.add_field("collection1", "SequenceName", str)
                session.add_field("collection1", "PatientName", str)
                session.add_field("collection1", "BandWidth", float)

                # Adding documents
                session.add_document("collection1", "document1")
                session.add_document("collection1", "document2")

                # Adding values
                session.add_value("collection1", "document1", "SequenceName", "Flash")
                session.add_value("collection1", "document1", "PatientName", "Guerbet")
                session.add_value("collection1", "document1", "BandWidth", 50000)
                self.assertEqual(session.get_value("collection1", "document1", "SequenceName"), "Flash")
                self.assertEqual(session.get_value("collection1", "document1", "PatientName"), "Guerbet")
                self.assertEqual(session.get_value("collection1", "document1", "BandWidth"), 50000)

                # Setting all values
                values = {}
                values["PatientName"] = "Patient"
                values["BandWidth"] = 25000
                session.set_values("collection1", "document1", values)
                self.assertEqual(session.get_value("collection1", "document1", "PatientName"), "Patient")
                self.assertEqual(session.get_value("collection1", "document1", "BandWidth"), 25000)

                # Testing that the primary_key cannot be set
                values = {}
                values["index"] = "document3"
                values["BandWidth"] = 25000
                self.assertRaises(ValueError, lambda : session.set_values("collection1", "document1", values))

                # Trying with the field not existing
                values = {}
                values["PatientName"] = "Patient"
                values["BandWidth"] = 25000
                values["Field_not_existing"] = "value"
                self.assertRaises(ValueError, lambda : session.set_values("collection1", "document1", values))

                # Trying with invalid values
                values = {}
                values["PatientName"] = 50
                values["BandWidth"] = 25000
                self.assertRaises(ValueError, lambda : session.set_values("collection1", "document1", values))
                self.assertRaises(Exception, lambda: session.set_values("collection1", "document1", True))

                # Trying with the collection not existing
                values = {}
                values["PatientName"] = "Guerbet"
                values["BandWidth"] = 25000
                self.assertRaises(ValueError, lambda : session.set_values("collection_not_existing", "document1", values))

                # Trying with the document not existing
                values = {}
                values["PatientName"] = "Guerbet"
                values["BandWidth"] = 25000
                self.assertRaises(ValueError, lambda : session.set_values("collection1", "document_not_existing", values))

                # Testing with list values
                session.add_field("collection1", "list1", list[str])
                session.add_field("collection1", "list2", list[int])
                session.add_value("collection1", "document1", "list1", ["a", "b", "c"])
                session.add_value("collection1", "document1", "list2", [1, 2, 3])
                values = {}
                values["list1"] = ["a", "a", "a"]
                values["list2"] = [1, 1, 1]
                session.set_values("collection1", "document1", values)
                self.assertEqual(session.get_value("collection1", "document1", "list1"), ["a", "a", "a"])
                self.assertEqual(session.get_value("collection1", "document1", "list2"), [1, 1, 1])

        def test_get_field_names(self):
            """
            Tests the method removing a value
            """

            database = self.create_database()
            with database as session:
                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding a field
                session.add_field("collection1", "PatientName", str,
                                  "Name of the patient")

                fields = session.get_fields_names("collection1")
                self.assertEqual(len(fields), 2)
                self.assertTrue("name" in fields)
                self.assertTrue("PatientName" in fields)

                session.add_field("collection1", "SequenceName", str,
                                  "Name of the patient")

                fields = session.get_fields_names("collection1")
                self.assertEqual(len(fields), 3)
                self.assertTrue("name" in fields)
                self.assertTrue("PatientName" in fields)
                self.assertTrue("SequenceName" in fields)

                # Adding a second collection
                session.add_collection("collection2", "id")

                fields = session.get_fields_names("collection1")
                self.assertEqual(len(fields), 3)
                self.assertTrue("name" in fields)
                self.assertTrue("PatientName" in fields)
                self.assertTrue("SequenceName" in fields)

                # Testing with a collection not existing
                self.assertEqual(session.get_fields_names("collection_not_existing"), [])

        def test_get_value(self):
            """
            Tests the method giving the current value, given a document and a field
            """

            database = self.create_database()
            with database as session:
                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding documents
                document = {}
                document["name"] = "document1"
                session.add_document("collection1", document)

                # Adding fields
                session.add_field("collection1", "PatientName", str,
                                  "Name of the patient")
                session.add_field("collection1", "Dataset dimensions", list[int],
                                  None)
                session.add_field("collection1", "Bits per voxel", int, None)
                session.add_field("collection1", "Grids spacing", list[float], None)

                # Adding values
                session.add_value("collection1", "document1", "PatientName", "test")
                session.add_value("collection1", "document1", "Bits per voxel", 10)
                session.add_value(
                    "collection1", "document1", "Dataset dimensions", [3, 28, 28, 3])
                session.add_value("collection1", "document1", "Grids spacing", [
                    0.234375, 0.234375, 0.4])

                # Testing that the value is returned if it exists
                self.assertEqual(session.get_value(
                    "collection1", "document1", "PatientName"), "test")
                self.assertEqual(session.get_value(
                    "collection1", "document1", "Bits per voxel"), 10)
                self.assertEqual(session.get_value(
                    "collection1", "document1", "Dataset dimensions"), [3, 28, 28, 3])
                self.assertEqual(session.get_value(
                    "collection1", "document1", "Grids spacing"), [0.234375, 0.234375, 0.4])

                # Testing when the value is not existing
                self.assertIsNone(session.get_value("collection_not_existing", "document1", "PatientName"))
                self.assertIsNone(session.get_value("collection1", "document3", "PatientName"))
                self.assertIsNone(session.get_value("collection1", "document1", "NotExisting"))
                self.assertIsNone(session.get_value("collection1", "document3", "NotExisting"))
                self.assertIsNone(session.get_value("collection1", "document2", "Grids spacing"))

                # Testing with wrong parameters
                self.assertIsNone(session.get_value(3, "document1", "Grids spacing"))
                self.assertIsNone(session.get_value("collection1", 1, "Grids spacing"))
                self.assertIsNone(session.get_value("collection1", "document1", None))
                self.assertIsNone(session.get_value("collection1", 3.5, None))

        def test_check_type_value(self):
            """
            Tests the method checking the validity of incoming values
            """

            database = self.create_database()
            with database as session:
                self.assertTrue(check_value_type("string", str))
                self.assertFalse(check_value_type(1, str))
                self.assertTrue(check_value_type(None, str))
                self.assertTrue(check_value_type(1, int))
                self.assertTrue(check_value_type(1, float))
                self.assertTrue(check_value_type(1.5, float))
                self.assertTrue(check_value_type([1.5], list[float]))
                self.assertFalse(check_value_type(1.5, list[float]))
                self.assertFalse(check_value_type([1.5, "test"], list[float]))
                value = {}
                value["test1"] = 1
                value["test2"] = 2
                self.assertTrue(check_value_type(value, dict))
                value2 = {}
                value2["test3"] = 1
                value2["test4"] = 2
                self.assertTrue(check_value_type([value, value2], list[dict]))

        def test_add_value(self):
            """
            Tests the method adding a value
            """

            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding documents
                document = {}
                document["name"] = "document1"
                session.add_document("collection1", document)
                document = {}
                document["name"] = "document2"
                session.add_document("collection1", document)

                # Adding fields
                session.add_field("collection1", "PatientName", str,
                                  "Name of the patient")
                session.add_field(
                    "collection1", "Bits per voxel", int, None)
                session.add_field("collection1", "BandWidth", float, None)
                session.add_field("collection1", "AcquisitionTime", time, None)
                session.add_field("collection1", "AcquisitionDate", datetime, None)
                session.add_field("collection1", "Dataset dimensions", list[int],
                                  None)
                session.add_field("collection1", "Grids spacing", list[float], None)
                session.add_field("collection1", "Boolean", bool, None)
                session.add_field("collection1", "Boolean list", list[bool], None)


                # Adding values
                collection1 = session["collection1"]

                document1 = collection1["document1"]
                document1["PatientName"] = "test"
                document1["Bits per voxel"] = 1
                document1["Dataset dimensions"] = [3, 28, 28, 3]
                document1["Boolean"] = True
                d = datetime(2014, 2, 11, 8, 5, 7)
                document1["AcquisitionDate"] = d
                t = datetime(2014, 2, 11, 0, 2, 2).time()
                document1["AcquisitionTime"] = t
                document1["BandWidth"] = 45
                collection1["document1"] = document1

                document2 = collection1["document2"]
                document2["Grids spacing"] = [0.234375, 0.234375, 0.4]
                document2["BandWidth"] = 35.5
                collection1["document2"] = document2


                # Testing that the values are actually added
                document1 = session["collection1"]["document1"]
                document2 = session["collection1"]["document2"]
                self.assertEqual(document1["PatientName"], "test")
                self.assertEqual(document2["BandWidth"], 35.5)
                self.assertEqual(document1["Bits per voxel"], 1)
                self.assertEqual(document1["BandWidth"], 45)
                self.assertEqual(document1["AcquisitionDate"], d)
                self.assertEqual(document1["AcquisitionTime"], t)
                self.assertEqual(document1["Dataset dimensions"], [3, 28, 28, 3])
                self.assertEqual(document2["Grids spacing"], [0.234375, 0.234375, 0.4])
                self.assertEqual(document1["Boolean"], True)


        def test_get_document(self):
            """
            Tests the method giving the document row given a document
            """

            database = self.create_database()
            with database as session:
                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding a document
                document = {}
                document["name"] = "document1"
                session.add_document("collection1", document)

                # Testing that a document is returned if it exists
                self.assertIsNotNone(session.get_document("collection1", "document1"))
                
                # Testing that None is returned if the document does not exist
                self.assertIsNone(session.get_document("collection1", "document3"))

                # Testing that None is returned if the collection does not exist
                self.assertIsNone(session.get_document("collection_not_existing", "document1"))

                # Testing with wrong parameters
                self.assertIsNone(session.get_document(False, "document1"))
                self.assertIsNone(session.get_document("collection1", None))
                self.assertIsNone(session.get_document("collection1", 1))

        def test_remove_document(self):
            """
            Tests the method removing a document
            """
            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding documents
                document = {}
                document["name"] = "document1"
                session.add_document("collection1", document)
                document = {}
                document["name"] = "document2"
                session.add_document("collection1", document)

                # Adding a field
                session.add_field("collection1", "PatientName", str,
                                  "Name of the patient")
                session.add_field("collection1", "FOV", list[int], None)

                # Adding a value
                session.add_value("collection1", "document1", "PatientName", "test")
                session.add_value("collection1", "document1", "FOV", [1, 2, 3])

                # Removing a document
                session.remove_document("collection1", "document1")

                # Testing that the document is removed from all tables
                self.assertIsNone(session.get_document("collection1", "document1"))

                # Testing that the values associated are removed
                self.assertIsNone(session.get_value("collection1", "document1", "PatientName"))

                # Testing with a collection not existing
                self.assertRaises(ValueError, lambda : session.remove_document("collection_not_existing", "document1"))

                # Testing with a document not existing
                self.assertRaises(ValueError, lambda : session.remove_document("collection1", "NotExisting"))

                # Removing a document
                session.remove_document("collection1", "document2")

                # Testing that the document is removed from the collection
                self.assertIsNone(session.get_document("collection1", "document2"))

                # Trying to remove the document a second time
                self.assertRaises(ValueError, lambda : session.remove_document("collection1", "document1"))

        def test_add_document(self):
            """
            Tests the method adding a document
            """

            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding fields
                session.add_field("collection1", "List", list[int])
                session.add_field("collection1", "Int", int)

                # Adding a document
                document = {}
                document["name"] = "document1"
                document["List"] = [1, 2, 3]
                document["Int"] = 5
                session.add_document("collection1", document)

                # Testing that the document has been added
                document = session.get_document("collection1", "document1")
                self.assertEqual(document["name"], "document1")

                # Testing when trying to add a document that already exists
                document = {}
                document["name"] = "document1"
                with self.assertRaises(Exception):
                    session.add_document("collection1", document)

                # Testing with invalid parameters
                self.assertRaises(ValueError, lambda : session.add_document(15, "document1"))
                self.assertRaises(ValueError, lambda : session.add_document("collection_not_existing", "document1"))
                self.assertRaises(Exception, lambda : session.add_document("collection1", True))

                # Testing the add of several documents
                document = {}
                document["name"] = "document2"
                session.add_document("collection1", document)

                # Adding a document with a dictionary without the primary key
                document = {}
                document["no_primary_key"] = "document1"
                with self.assertRaises(Exception):
                    session.add_document("collection1", document)

        def test_add_collection(self):
            """
            Tests the method adding a collection
            """

            database = self.create_database()
            with database as session:

                # Adding a first collection
                session.add_collection("collection1")

                # Checking values
                collection = session.get_collection("collection1")
                self.assertEqual(collection.name, "collection1")
                self.assertEqual(collection.primary_key, {"primary_key": str})

                # Adding a second collection
                session.add_collection("collection2", "id")

                # Checking values
                collection = session.get_collection("collection2")
                self.assertEqual(collection.name, "collection2")
                self.assertEqual(collection.primary_key, {"id": str})

                # Trying with a collection already existing
                self.assertRaises(Exception, lambda : session.add_collection("collection1"))

                # Trying with table names already taken
                session.add_field("collection1", "test", str, description='Test field')
                self.assertRaises(Exception, lambda : session.add_collection(session.populse_db_table))

                # Trying with wrong types
                self.assertRaises(Exception, lambda: session.add_collection("collection_valid", True))

        def test_remove_collection(self):
            """
            Tests the method removing a collection
            """

            database = self.create_database()
            with database as session:

                # Adding a first collection
                session.add_collection("collection1")

                # Checking values
                collection = session.get_collection("collection1")
                self.assertEqual(collection.collection_name, "collection1")
                self.assertEqual(collection.primary_key, "index")

                # Removing a collection
                session.remove_collection("collection1")

                # Testing that it does not exist anymore
                self.assertIsNone(session.get_collection("collection1"))

                # Adding new collections
                session.add_collection("collection1")
                session.add_collection("collection2")

                # Checking values
                collection = session.get_collection("collection1")
                self.assertEqual(collection.collection_name, "collection1")
                self.assertEqual(collection.primary_key, "index")
                collection = session.get_collection("collection2")
                self.assertEqual(collection.collection_name, "collection2")
                self.assertEqual(collection.primary_key, "index")

                # Removing one collection and testing that the other is unchanged
                session.remove_collection("collection2")
                collection = session.get_collection("collection1")
                self.assertEqual(collection.collection_name, "collection1")
                self.assertEqual(collection.primary_key, "index")
                self.assertIsNone(session.get_collection("collection2"))

                # Adding a field
                session.add_field("collection1", "Field", str)
                field = session.get_field("collection1", "Field")
                self.assertEqual(field.field_name, "Field")
                self.assertEqual(field.collection_name, "collection1")
                self.assertIsNone(field.description)
                self.assertEqual(field.field_type, str)

                # Adding a document
                session.add_document("collection1", "document")
                document = session.get_document("collection1", "document")
                self.assertEqual(document.index, "document")

                # Removing the collection containing the field and the document and testing that it is indeed removed
                session.remove_collection("collection1")
                self.assertIsNone(session.get_collection("collection1"))
                self.assertIsNone(session.get_field("collection1", "name"))
                self.assertIsNone(session.get_field("collection1", "Field"))
                self.assertIsNone(session.get_document("collection1", "document"))

                # Testing with a collection not existing
                self.assertRaises(ValueError, lambda : session.remove_collection("collection_not_existing"))
                self.assertRaises(ValueError, lambda : session.remove_collection(True))

        def test_get_collection(self):
            """
            Tests the method giving the collection row
            """

            database = self.create_database()
            with database as session:
                # Adding a first collection
                session.add_collection("collection1")

                # Checking values
                collection = session.get_collection("collection1")
                self.assertEqual(collection.collection_name, "collection1")
                self.assertEqual(collection.primary_key, "index")

                # Adding a second collection
                session.add_collection("collection2", "id")

                # Checking values
                collection = session.get_collection("collection2")
                self.assertEqual(collection.collection_name, "collection2")
                self.assertEqual(collection.primary_key, "id")

                # Trying with a collection not existing
                self.assertIsNone(session.get_collection("collection3"))

                # Trying with a table name already existing
                self.assertIsNone(session.get_collection("collection"))
                self.assertIsNone(session.get_collection("field"))

        def test_get_collections(self):
            """
            Tests the method giving the list of collections rows
            """

            database = self.create_database()
            with database as session:
                # Testing that there is no collection at first
                self.assertEqual(session.get_collections(), [])

                # Adding a collection
                session.add_collection("collection1")

                collections = session.get_collections()
                self.assertEqual(len(collections), 1)
                self.assertEqual(collections[0].collection_name, "collection1")

                session.add_collection("collection2")

                collections = session.get_collections()
                self.assertEqual(len(collections), 2)

                session.remove_collection("collection2")

                collections = session.get_collections()
                self.assertEqual(len(collections), 1)
                self.assertEqual(collections[0].collection_name, "collection1")

        def test_get_collections_names(self):
            """
            Tests the method giving the collections names
            """

            database = self.create_database()
            with database as session:
                # Testing that there is no collection at first
                self.assertEqual(session.get_collections_names(), [])

                # Adding a collection
                session.add_collection("collection1")

                self.assertEqual(session.get_collections_names(), ["collection1"])

                session.add_collection("collection2")

                collections = session.get_collections_names()
                self.assertEqual(len(collections), 2)
                self.assertTrue("collection1" in collections)
                self.assertTrue("collection2" in collections)

                session.remove_collection("collection2")

                self.assertEqual(session.get_collections_names(), ["collection1"])

        def test_get_documents(self):
            """
            Tests the method returning the list of document rows, given a collection
            """

            database = self.create_database()
            with database as session:
                # Adding collections
                session.add_collection("collection1", "name")
                session.add_collection("collection2", "id")

                session.add_document("collection1", "document1")
                session.add_document("collection1", "document2")
                session.add_document("collection2", "document1")
                session.add_document("collection2", "document2")

                documents1 = session.get_documents("collection1")
                self.assertEqual(len(documents1), 2)

                documents2 = session.get_documents("collection2")
                self.assertEqual(len(documents2), 2)

                # Testing with a collection not existing
                self.assertEqual(session.get_documents("collection_not_existing"), [])
                self.assertEqual(session.get_documents("collection"), [])
                self.assertEqual(session.get_documents(None), [])

        def test_get_documents_names(self):
            """
            Tests the method returning the list of document names, given a collection
            """

            database = self.create_database()
            with database as session:
                # Adding collections
                session.add_collection("collection1", "name")
                session.add_collection("collection2", "FileName")

                session.add_document("collection1", "document1")
                session.add_document("collection1", "document2")
                session.add_document("collection2", "document3")
                session.add_document("collection2", "document4")

                documents1 = session.get_documents_names("collection1")
                self.assertEqual(len(documents1), 2)
                self.assertTrue("document1" in documents1)
                self.assertTrue("document2" in documents1)

                documents2 = session.get_documents_names("collection2")
                self.assertEqual(len(documents2), 2)
                self.assertTrue("document3" in documents2)
                self.assertTrue("document4" in documents2)

                # Testing with a collection not existing
                self.assertEqual(session.get_documents_names("collection_not_existing"), [])
                self.assertEqual(session.get_documents_names("collection"), [])
                self.assertEqual(session.get_documents_names(None), [])

        def test_remove_value(self):
            """
            Tests the method removing a value
            """

            database = self.create_database()
            with database as session:

                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding a document
                session.add_document("collection1", "document1")

                # Adding fields
                session.add_field("collection1", "PatientName", str,
                                  "Name of the patient")
                session.add_field("collection1", "Bits per voxel", int, None)
                session.add_field("collection1", "Dataset dimensions",
                                  list[int], None)

                # Adding values
                session.add_value("collection1", "document1", "PatientName", "test")

                self.assertRaises(ValueError, lambda : session.add_value("collection1", "document1", "Bits per voxel", "space_field"))
                session.add_value("collection1", "document1", "Dataset dimensions", [3, 28, 28, 3])
                value = session.get_value("collection1", "document1", "Dataset dimensions")
                self.assertEqual(value, [3, 28, 28, 3])

                # Removing values
                session.remove_value("collection1", "document1", "PatientName")
                session.remove_value("collection1", "document1", "Bits per voxel")
                session.remove_value("collection1", "document1", "Dataset dimensions")

                # Testing when not existing
                self.assertRaises(ValueError, lambda : session.remove_value("collection_not_existing", "document1", "PatientName"))
                self.assertRaises(ValueError, lambda : session.remove_value("collection1", "document3", "PatientName"))
                self.assertRaises(ValueError, lambda : session.remove_value("collection1", "document1", "NotExisting"))
                self.assertRaises(ValueError, lambda : session.remove_value("collection1", "document3", "NotExisting"))

                # Testing that the values are actually removed
                self.assertIsNone(session.get_value("collection1", "document1", "PatientName"))
                self.assertIsNone(session.get_value("collection1", "document1", "Bits per voxel"))
                self.assertIsNone(session.get_value("collection1", "document1", "Dataset dimensions"))

        def test_list_dates(self):
            """
            Tests the storage and retrieval of fields of type list of time, date
            and datetime
            """

            database = self.create_database()
            with database as session:
                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding fields
                session.add_field("collection1", "list_date", list[date], None)
                session.add_field("collection1", "list_time", list[time], None)
                session.add_field("collection1", "list_datetime", list[datetime], None)

                document = {}
                document["name"] = "document1"
                session.add_document("collection1", document)

                list_date = [date(2018, 5, 23), date(1899, 12, 31)]
                list_time = [time(12, 41, 33, 540), time(1, 2, 3)]
                list_datetime = [datetime(2018, 5, 23, 12, 41, 33, 540),
                                 datetime(1899, 12, 31, 1, 2, 3)]

                session.add_value("collection1", "document1", "list_date", list_date)
                self.assertEqual(
                    list_date, session.get_value("collection1", "document1", "list_date"))
                session.add_value("collection1", "document1", "list_time", list_time)
                self.assertEqual(
                    list_time, session.get_value("collection1", "document1", "list_time"))
                session.add_value("collection1", "document1", "list_datetime", list_datetime)
                self.assertEqual(list_datetime, session.get_value(
                    "collection1", "document1", "list_datetime"))

        def test_json_field(self):
            """
            Tests the storage and retrieval of fields of type JSON
            """

            doc = {"name": "the_name",
                    "json": {"key": [1, 2, "three"]}}
            database = self.create_database()
            with database as session:
                # Adding a collection
                session.add_collection("collection1", "name")

                # Adding fields
                session.add_field("collection1", "json", dict)
                
                session.add_document("collection1", doc)
                self.assertEqual(doc, session.get_document("collection1", "the_name")._dict())
                self.assertIsNone(session.get_document("collection1", "not_a_valid_name"))

            with database as session:
                self.assertEqual(doc, session.get_document("collection1", "the_name")._dict())
                self.assertIsNone(session.get_document("collection1", "not_a_valid_name"))
                
        def test_filter_documents(self):
            """
            Tests the method applying the filter
            """

            database = self.create_database()
            with database as session:

                session.add_collection("collection_test")
                session.add_field("collection_test", "field_test", str, None)
                session["collection_test"]["document_test"] = {}

                # Checking with invalid collection
                self.assertRaises(ValueError, lambda : set(document["primary_key"] for document in session.filter_documents("collection_not_existing", None)))

                # Checking that every document is returned if there is no filter
                documents = set(document["primary_key"] for document in session.filter_documents("collection_test", None))
                self.assertEqual(documents, set(['document_test']))

        def test_filters(self):
            list_datetime = [datetime(2018, 5, 23, 12, 41, 33, 540),
                             datetime(1981, 5, 8, 20, 0),
                             datetime(1899, 12, 31, 1, 2, 3)]

            database = self.create_database()
            with database as session:
                session.add_collection("collection1", "name")

                session.add_field("collection1", 'format', field_type=str,
                                  description=None, index=True)
                session.add_field("collection1", 'strings', field_type=list[str],
                                  description=None)
                session.add_field("collection1", 'datetime', field_type=datetime,
                                  description=None)
                session.add_field("collection1", 'has_format', field_type=bool,
                                  description=None)

                files = ('abc', 'bcd', 'def', 'xyz')
                for file in files:
                    for date in list_datetime:
                        for format, ext in (('NIFTI', 'nii'),
                                            ('DICOM', 'dcm'),
                                            ('Freesurfer', 'mgz')):
                            document = dict(
                                name='/%s_%d.%s' % (file, date.year, ext),
                                format=format,
                                strings=list(file),
                                datetime=date,
                                has_format=True,
                            )
                            session.add_document("collection1", document)
                        document = '/%s_%d.none' % (file, date.year)
                        d = dict(name=document, strings=list(file))
                        session.add_document("collection1", d)

                for filter, expected in (
                        ('format == "NIFTI"',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_2018.nii',
                             '/abc_2018.nii',
                             '/bcd_1899.nii',
                             '/bcd_2018.nii',
                             '/def_1899.nii',
                             '/abc_1981.nii',
                             '/def_2018.nii',
                             '/def_1981.nii',
                             '/bcd_1981.nii',
                             '/abc_1899.nii',
                             '/xyz_1981.nii'
                         ])
                         ),

                        ('"b" IN strings',
                         set([
                             '/bcd_2018.mgz',
                             '/abc_1899.mgz',
                             '/abc_1899.dcm',
                             '/bcd_1981.dcm',
                             '/abc_1981.dcm',
                             '/bcd_1981.mgz',
                             '/bcd_1899.mgz',
                             '/abc_1981.mgz',
                             '/abc_2018.mgz',
                             '/abc_2018.dcm',
                             '/bcd_2018.dcm',
                             '/bcd_1899.dcm',
                             '/abc_2018.nii',
                             '/bcd_1899.nii',
                             '/abc_1981.nii',
                             '/bcd_1981.nii',
                             '/abc_1899.nii',
                             '/bcd_2018.nii',
                             '/abc_1899.none',
                             '/bcd_1899.none',
                             '/bcd_1981.none',
                             '/abc_2018.none',
                             '/bcd_2018.none',
                             '/abc_1981.none'
                         ])
                         ),

                        ('(format == "NIFTI" OR NOT format == "DICOM")',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_1899.mgz',
                             '/bcd_2018.mgz',
                             '/bcd_1899.nii',
                             '/bcd_2018.nii',
                             '/def_1899.nii',
                             '/bcd_1981.mgz',
                             '/abc_1981.nii',
                             '/def_2018.mgz',
                             '/abc_1899.nii',
                             '/def_1899.mgz',
                             '/xyz_1899.none',
                             '/abc_2018.nii',
                             '/def_1899.none',
                             '/bcd_1899.mgz',
                             '/def_2018.nii',
                             '/abc_1981.mgz',
                             '/abc_1899.none',
                             '/xyz_1981.mgz',
                             '/bcd_1981.nii',
                             '/xyz_1981.nii',
                             '/abc_2018.mgz',
                             '/xyz_2018.nii',
                             '/abc_1899.mgz',
                             '/def_1981.nii',
                             '/def_1981.mgz',
                             '/bcd_1899.none',
                             '/xyz_2018.mgz',
                             '/bcd_1981.none',
                             '/xyz_1981.none',
                             '/abc_1981.none',
                             '/def_2018.none',
                             '/xyz_2018.none',
                             '/abc_2018.none',
                             '/def_1981.none',
                             '/bcd_2018.none'
                         ])
                         ),

                        ('"a" IN strings',
                         set([
                             '/abc_1899.none',
                             '/abc_1899.nii',
                             '/abc_2018.nii',
                             '/abc_1899.mgz',
                             '/abc_1899.dcm',
                             '/abc_1981.dcm',
                             '/abc_1981.nii',
                             '/abc_1981.mgz',
                             '/abc_2018.mgz',
                             '/abc_2018.dcm',
                             '/abc_2018.none',
                             '/abc_1981.none'
                         ])
                         ),

                        ('NOT "b" IN strings',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_2018.dcm',
                             '/def_1981.dcm',
                             '/xyz_2018.nii',
                             '/xyz_1981.dcm',
                             '/def_1899.none',
                             '/xyz_1899.dcm',
                             '/xyz_1981.nii',
                             '/def_1899.dcm',
                             '/def_1899.nii',
                             '/def_2018.mgz',
                             '/def_2018.nii',
                             '/xyz_1899.mgz',
                             '/def_2018.dcm',
                             '/def_1899.mgz',
                             '/def_1981.mgz',
                             '/xyz_1981.mgz',
                             '/xyz_2018.mgz',
                             '/xyz_1899.none',
                             '/def_1981.nii',
                             '/xyz_2018.none',
                             '/xyz_1981.none',
                             '/def_2018.none',
                             '/def_1981.none'
                         ])
                         ),
                        ('("a" IN strings OR NOT "b" IN strings)',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_1899.mgz',
                             '/def_1899.nii',
                             '/abc_1981.nii',
                             '/def_2018.mgz',
                             '/abc_1899.nii',
                             '/def_1899.mgz',
                             '/abc_2018.dcm',
                             '/xyz_1899.none',
                             '/xyz_2018.dcm',
                             '/def_1981.dcm',
                             '/abc_2018.nii',
                             '/def_1899.none',
                             '/abc_1981.dcm',
                             '/def_2018.nii',
                             '/abc_1981.mgz',
                             '/def_2018.dcm',
                             '/abc_1899.none',
                             '/xyz_1981.mgz',
                             '/xyz_1899.dcm',
                             '/abc_1899.dcm',
                             '/def_1899.dcm',
                             '/xyz_1981.nii',
                             '/abc_2018.mgz',
                             '/xyz_2018.nii',
                             '/abc_1899.mgz',
                             '/xyz_1981.dcm',
                             '/def_1981.nii',
                             '/def_1981.mgz',
                             '/xyz_2018.mgz',
                             '/xyz_1981.none',
                             '/abc_1981.none',
                             '/def_2018.none',
                             '/xyz_2018.none',
                             '/abc_2018.none',
                             '/def_1981.none'
                         ])
                         ),

                        ('format IN ["DICOM", "NIFTI"]',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_2018.dcm',
                             '/bcd_1899.nii',
                             '/def_1899.nii',
                             '/abc_1981.nii',
                             '/abc_1899.nii',
                             '/bcd_2018.nii',
                             '/abc_2018.dcm',
                             '/bcd_1899.dcm',
                             '/def_1981.dcm',
                             '/abc_2018.nii',
                             '/abc_1981.dcm',
                             '/bcd_2018.dcm',
                             '/def_2018.nii',
                             '/def_2018.dcm',
                             '/xyz_1899.dcm',
                             '/abc_1899.dcm',
                             '/def_1899.dcm',
                             '/bcd_1981.nii',
                             '/xyz_1981.nii',
                             '/xyz_2018.nii',
                             '/xyz_1981.dcm',
                             '/def_1981.nii',
                             '/bcd_1981.dcm',
                         ])
                         ),

                        ('(format == "NIFTI" OR NOT format == "DICOM") AND ("a" IN strings OR NOT "b" IN strings)',
                         set([
                             '/abc_1899.none',
                             '/xyz_1899.mgz',
                             '/abc_1981.mgz',
                             '/abc_2018.nii',
                             '/xyz_1899.nii',
                             '/abc_1899.mgz',
                             '/def_1899.mgz',
                             '/def_1899.nii',
                             '/def_1899.none',
                             '/abc_1981.nii',
                             '/def_2018.nii',
                             '/xyz_2018.nii',
                             '/def_1981.nii',
                             '/abc_1899.nii',
                             '/xyz_1981.nii',
                             '/abc_2018.mgz',
                             '/def_1981.mgz',
                             '/xyz_2018.mgz',
                             '/xyz_1899.none',
                             '/def_2018.mgz',
                             '/xyz_1981.mgz',
                             '/xyz_1981.none',
                             '/abc_1981.none',
                             '/def_2018.none',
                             '/xyz_2018.none',
                             '/abc_2018.none',
                             '/def_1981.none'
                         ])
                         ),

                        ('format > "DICOM"',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_1899.mgz',
                             '/bcd_2018.mgz',
                             '/bcd_1899.nii',
                             '/bcd_2018.nii',
                             '/def_1899.nii',
                             '/bcd_1981.mgz',
                             '/abc_1981.nii',
                             '/def_2018.mgz',
                             '/abc_1899.nii',
                             '/def_1899.mgz',
                             '/abc_2018.nii',
                             '/def_2018.nii',
                             '/abc_1981.mgz',
                             '/xyz_1981.mgz',
                             '/bcd_1981.nii',
                             '/xyz_1981.nii',
                             '/abc_2018.mgz',
                             '/xyz_2018.nii',
                             '/abc_1899.mgz',
                             '/def_1981.nii',
                             '/def_1981.mgz',
                             '/bcd_1899.mgz',
                             '/xyz_2018.mgz'
                         ])
                         ),

                        ('format <= "DICOM"',
                         set([
                             '/abc_1981.dcm',
                             '/def_1899.dcm',
                             '/abc_2018.dcm',
                             '/bcd_1899.dcm',
                             '/def_1981.dcm',
                             '/bcd_2018.dcm',
                             '/def_2018.dcm',
                             '/xyz_2018.dcm',
                             '/xyz_1899.dcm',
                             '/abc_1899.dcm',
                             '/xyz_1981.dcm',
                             '/bcd_1981.dcm',
                         ])
                         ),

                        ('format > "DICOM" AND strings != ["b", "c", "d"]',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_1899.mgz',
                             '/abc_1981.mgz',
                             '/abc_2018.nii',
                             '/xyz_2018.nii',
                             '/abc_1899.mgz',
                             '/def_1899.mgz',
                             '/def_1899.nii',
                             '/abc_1981.nii',
                             '/def_2018.nii',
                             '/def_1981.nii',
                             '/abc_1899.nii',
                             '/xyz_1981.nii',
                             '/abc_2018.mgz',
                             '/def_1981.mgz',
                             '/xyz_2018.mgz',
                             '/def_2018.mgz',
                             '/xyz_1981.mgz'
                         ])
                         ),

                        ('format <= "DICOM" AND strings == ["b", "c", "d"]',
                         set([
                             '/bcd_2018.dcm',
                             '/bcd_1981.dcm',
                             '/bcd_1899.dcm',
                         ])
                         ),

                        ('has_format in [false, null]',
                         set([
                             '/def_1899.none',
                             '/abc_1899.none',
                             '/bcd_1899.none',
                             '/xyz_1899.none',
                             '/bcd_2018.none',
                             '/abc_1981.none',
                             '/def_2018.none',
                             '/xyz_2018.none',
                             '/abc_2018.none',
                             '/def_1981.none',
                             '/xyz_1981.none',
                             '/bcd_1981.none',
                         ])
                         ),

                        ('format == null',
                         set([
                             '/bcd_1981.none',
                             '/abc_1899.none',
                             '/def_1899.none',
                             '/bcd_2018.none',
                             '/abc_1981.none',
                             '/def_2018.none',
                             '/xyz_2018.none',
                             '/abc_2018.none',
                             '/def_1981.none',
                             '/bcd_1899.none',
                             '/xyz_1899.none',
                             '/xyz_1981.none'
                         ])
                         ),

                        ('strings == null',
                         set()),

                        ('strings != NULL',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_2018.dcm',
                             '/xyz_1899.mgz',
                             '/bcd_2018.mgz',
                             '/bcd_1899.nii',
                             '/def_2018.none',
                             '/def_1899.mgz',
                             '/def_1899.nii',
                             '/bcd_1981.mgz',
                             '/abc_1981.nii',
                             '/def_2018.mgz',
                             '/abc_1899.nii',
                             '/bcd_2018.nii',
                             '/abc_2018.dcm',
                             '/xyz_1899.none',
                             '/bcd_1899.dcm',
                             '/bcd_1981.none',
                             '/def_1981.dcm',
                             '/abc_2018.nii',
                             '/def_1899.none',
                             '/xyz_1981.none',
                             '/abc_1981.dcm',
                             '/bcd_2018.dcm',
                             '/def_2018.nii',
                             '/abc_1981.mgz',
                             '/def_2018.dcm',
                             '/abc_1899.none',
                             '/xyz_1981.mgz',
                             '/xyz_1899.dcm',
                             '/abc_1899.dcm',
                             '/def_1899.dcm',
                             '/bcd_1981.nii',
                             '/def_1981.none',
                             '/xyz_1981.nii',
                             '/abc_2018.mgz',
                             '/xyz_2018.none',
                             '/xyz_2018.nii',
                             '/abc_1899.mgz',
                             '/bcd_1899.mgz',
                             '/bcd_2018.none',
                             '/abc_1981.none',
                             '/xyz_1981.dcm',
                             '/abc_2018.none',
                             '/def_1981.nii',
                             '/bcd_1981.dcm',
                             '/def_1981.mgz',
                             '/bcd_1899.none',
                             '/xyz_2018.mgz'
                         ])
                         ),

                        ('format != NULL',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_1899.mgz',
                             '/bcd_2018.mgz',
                             '/bcd_1899.nii',
                             '/def_1899.mgz',
                             '/def_1899.nii',
                             '/bcd_1981.mgz',
                             '/abc_1981.nii',
                             '/def_2018.mgz',
                             '/abc_1899.nii',
                             '/bcd_2018.nii',
                             '/abc_2018.dcm',
                             '/xyz_1981.mgz',
                             '/def_1981.dcm',
                             '/abc_2018.nii',
                             '/abc_1981.dcm',
                             '/bcd_2018.dcm',
                             '/def_2018.nii',
                             '/bcd_1981.nii',
                             '/abc_1981.mgz',
                             '/def_2018.dcm',
                             '/bcd_1899.dcm',
                             '/xyz_2018.dcm',
                             '/xyz_1899.dcm',
                             '/abc_1899.dcm',
                             '/def_1899.dcm',
                             '/bcd_1899.mgz',
                             '/xyz_1981.nii',
                             '/abc_2018.mgz',
                             '/xyz_2018.nii',
                             '/abc_1899.mgz',
                             '/xyz_1981.dcm',
                             '/def_1981.nii',
                             '/bcd_1981.dcm',
                             '/def_1981.mgz',
                             '/xyz_2018.mgz'
                         ])
                         ),

                        ('name like "%.nii"',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_2018.nii',
                             '/abc_2018.nii',
                             '/bcd_1899.nii',
                             '/bcd_2018.nii',
                             '/def_1899.nii',
                             '/abc_1981.nii',
                             '/def_2018.nii',
                             '/def_1981.nii',
                             '/bcd_1981.nii',
                             '/abc_1899.nii',
                             '/xyz_1981.nii'
                         ])
                         ),

                        ('name ilike "%A%"',
                         set([
                             '/abc_1899.none',
                             '/abc_1899.nii',
                             '/abc_2018.nii',
                             '/abc_1899.mgz',
                             '/abc_1899.dcm',
                             '/abc_1981.dcm',
                             '/abc_1981.nii',
                             '/abc_1981.mgz',
                             '/abc_2018.mgz',
                             '/abc_2018.dcm',
                             '/abc_2018.none',
                             '/abc_1981.none'
                         ])
                         ),

                        ('all',
                         set([
                             '/xyz_1899.nii',
                             '/xyz_2018.dcm',
                             '/xyz_1899.mgz',
                             '/bcd_2018.mgz',
                             '/bcd_1899.nii',
                             '/def_2018.none',
                             '/def_1899.mgz',
                             '/def_1899.nii',
                             '/bcd_1981.mgz',
                             '/abc_1981.nii',
                             '/def_2018.mgz',
                             '/abc_1899.nii',
                             '/bcd_2018.nii',
                             '/abc_2018.dcm',
                             '/xyz_1899.none',
                             '/bcd_1899.dcm',
                             '/bcd_1981.none',
                             '/def_1981.dcm',
                             '/abc_2018.nii',
                             '/def_1899.none',
                             '/xyz_1981.none',
                             '/abc_1981.dcm',
                             '/bcd_2018.dcm',
                             '/def_2018.nii',
                             '/abc_1981.mgz',
                             '/def_2018.dcm',
                             '/abc_1899.none',
                             '/xyz_1981.mgz',
                             '/xyz_1899.dcm',
                             '/abc_1899.dcm',
                             '/def_1899.dcm',
                             '/bcd_1981.nii',
                             '/def_1981.none',
                             '/xyz_1981.nii',
                             '/abc_2018.mgz',
                             '/xyz_2018.none',
                             '/xyz_2018.nii',
                             '/abc_1899.mgz',
                             '/bcd_1899.mgz',
                             '/bcd_2018.none',
                             '/abc_1981.none',
                             '/xyz_1981.dcm',
                             '/abc_2018.none',
                             '/def_1981.nii',
                             '/bcd_1981.dcm',
                             '/def_1981.mgz',
                             '/bcd_1899.none',
                             '/xyz_2018.mgz'
                         ])
                         )):
                    for tested_filter in (filter, '(%s) AND ALL' % filter, 'ALL AND (%s)' % filter):
                        try:
                            documents = set(document.name for document in session.filter_documents("collection1", tested_filter))
                            self.assertEqual(documents, expected)
                        except Exception as e:
                            e.message = 'While testing filter : %s\n%s' % (str(tested_filter), str(e))
                            e.args = (e.message,)
                            raise
                    all_documents = set(document.name for document in session.filter_documents("collection1", 'ALL'))
                    for tested_filter in ('(%s) OR ALL' % filter, 'ALL OR (%s)' % filter):
                        try:
                            documents = set(document.name for document in session.filter_documents("collection1", tested_filter))
                            self.assertEqual(documents, all_documents)
                        except Exception as e:
                            e.message = 'While testing filter : %s\n%s' % (str(tested_filter), str(e))
                            e.args = (e.message,)
                            raise

        def test_modify_list_field(self):
            database = self.create_database()
            with database as session:
                session.add_collection("collection1", "name")
                session.add_field("collection1", 'strings', field_type=list[str],
                                  description=None)
                session.add_document("collection1", 'test')
                session.add_value("collection1", 'test', 'strings', ['a', 'b', 'c'])
                names = list(document.name for document in session.filter_documents("collection1", '"b" IN strings'))
                self.assertEqual(names, ['test'])

                session.set_value("collection1", 'test', 'strings', ['x', 'y', 'z'])
                names = list(document.name for document in session.filter_documents("collection1", '"b" IN strings'))
                self.assertEqual(names, [])
                names = list(document.name for document in session.filter_documents("collection1", '"z" IN strings'))
                self.assertEqual(names, ['test'])

                session.remove_value("collection1", 'test', 'strings')
                names = list(document.name for document in session.filter_documents("collection1", '"y" IN strings'))
                self.assertEqual(names, [])

        def test_filter_literals(self):
            """
            Test the Python values returned (internaly) for literals by the
            interpretor of filter expression 
            """

            literals = {
                'True': True,
                'TRUE': True,
                'true': True,
                'False': False,
                'FALSE': False,
                'false': False,
                'Null': None,
                'null': None,
                'Null': None,
                '0': 0,
                '123456789101112': 123456789101112,
                '-45': -45,
                '-46.8': -46.8,
                '1.5654353456363e-15': 1.5654353456363e-15,
                '""': '',
                '"2018-05-25"': '2018-05-25',
                '"a\n b\n  c"': 'a\n b\n  c',
                '"\\""': '"',
                '2018-05-25': date(2018, 5, 25),
                '2018-5-25': date(2018, 5, 25),
                '12:54': time(12, 54),
                '02:4:9': time(2, 4, 9),
                # The following interpretation of microsecond is a strange
                # behavior of datetime.strptime that expect up to 6 digits
                # with zeroes padded on the right !?
                '12:34:56.789': time(12, 34, 56, 789000),
                '12:34:56.000789': time(12, 34, 56, 789),
                '2018-05-25T12:34:56.000789': datetime(2018, 5, 25, 12, 34, 56, 789),
                '2018-5-25T12:34': datetime(2018, 5, 25, 12, 34),
                '[]': [],
            }
            # Adds the literal for a list of all elements in the dictionary
            literals['[%s]' % ','.join(literals.keys())] = list(literals.values())

            parser = literal_parser()
            for literal, expected_value in literals.items():
                tree = parser.parse(literal)
                value = FilterToSQL(None).transform(tree)
                self.assertEqual(value, expected_value)

        def test_with(self):
            """
            Tests the database session
            """

            database = self.create_database()
            try:
                with database as session:
                    session.add_collection("collection1", "name")
                    session.add_document("collection1", {"name": "toto"})
                    boom  # Raises an exception, modifications are rolled back
            except NameError:
                pass

            with database as session:
                session.add_collection("collection1", "name")
                session.add_document("collection1", {"name": "titi"})

            # Reopen the database to check that "titi" was commited
            database = self.create_database(clear=False)
            with database as session:
                names = [i.name for i in session.filter_documents("collection1", "all")]
                self.assertEqual(names, ['titi'])

                # Check that recursive session creation always return the
                # same object
                with database as session2:
                    self.assertIs(session, session2)
                    with database as session3:
                        self.assertIs(session, session3)
                        session.add_document("collection1", {"name": "toto"})

            # Check that previous session was commited but preserved
            # as long as the database is not destroyed.
            with database as session4:
                self.assertIs(session, session4)
        
            # Destroy the database and create a new one
            database = self.create_database(clear=False)

            # Check that previous session was destroyed and that
            # a new one is created.
            with database as session5:
                self.assertIsNot(session, session5)
                self.assertEqual(len(session5.get_documents('collection1')), 2)
        
        def test_automatic_fields_creation(self):
            """
            Test automatic creation of fields with add_document
            """
            database = self.create_database()
            with database as session:
                now = datetime.now()
                session.add_collection('test')
                base_doc = {
                    'string': 'string',
                    'int': 1,
                    'float': 1.4,
                    'boolean': True,
                    'datetime': now,
                    'date': now.date(),
                    'time': now.time(),
                    'dict': {
                        'string': 'string',
                        'int': 1,
                        'float': 1.4,
                        'boolean': True,
                    }
                }
                doc = base_doc.copy()
                for k, v in base_doc.items():
                    lk = 'list_%s' % k
                    doc[lk] = [v]
                doc['primary_key'] = 'test'
                session.add_document('test', doc)
                stored_doc = session.get_document('test', 'test')
                self.assertEqual(doc, stored_doc)
    
    return TestDatabaseMethods

def load_tests(loader, standard_tests, pattern):
    """
    Prepares the tests parameters

    :param loader:

    :param standard_tests:

    :param pattern:

    :return: A test suite
    """
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestsSQLiteInMemory))
    tests = loader.loadTestsFromTestCase(create_test_case())
    suite.addTests(tests)

    # Tests with postgresql. All the tests will be skiped if
    # it is not possible to connect to populse_db_tests database.
    #tests = loader.loadTestsFromTestCase(create_test_case(
        #database_url='postgresql:///populse_db_tests',
        #caches=False,
        #list_tables=True,
        #query_type='mixed'))
    #suite.addTests(tests)

    return suite


if __name__ == '__main__':

    # Working from the scripts directory
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    unittest.main()
