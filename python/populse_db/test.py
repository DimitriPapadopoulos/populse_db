import os
import shutil
import unittest
import tempfile
import datetime

from populse_db.database import Database
from populse_db.database_model import (create_database, TAG_ORIGIN_BUILTIN,
                                       TAG_TYPE_STRING, TAG_TYPE_FLOAT,
                                       TAG_UNIT_MHZ, TAG_TYPE_INTEGER,
                                       TAG_TYPE_TIME, TAG_TYPE_DATETIME,
                                       TAG_TYPE_LIST_STRING,
                                       TAG_TYPE_LIST_INTEGER,
                                       TAG_TYPE_LIST_FLOAT, PATH_TABLE,
                                       TAG_TYPE_LIST_DATE, TAG_TYPE_LIST_TIME,
                                       TAG_TYPE_LIST_DATETIME, TAG_TYPE_BOOLEAN, TAG_TYPE_LIST_BOOLEAN)


class TestDatabaseMethods(unittest.TestCase):
    """
    Class executing the unit tests of populse_db
    """

    def setUp(self):
        """
        Called before every unit test
        Creates a temporary folder containing the database file that will be used for the test
        """

        self.temp_folder = tempfile.mkdtemp()
        self.path = os.path.join(self.temp_folder, "test.db")
        self.string_engine = 'sqlite:///' + self.path

    def tearDown(self):
        """
        Called after every unit test
        Deletes the temporary folder created for the test
        """

        shutil.rmtree(self.temp_folder)
        
    def test_database_creation(self):
        """
        Tests the database creation
        """

        # Testing the creation of the database file
        create_database(self.string_engine)
        self.assertTrue(os.path.exists(self.path))

    def test_database_constructor(self):
        """
        Tests the database constructor
        """

        # Testing without the database file existing
        Database(self.string_engine)
        self.assertTrue(os.path.exists(self.path))

        # Testing with the database file existing
        os.remove(self.path)
        create_database(self.string_engine)
        Database(self.string_engine)
        self.assertTrue(os.path.exists(self.path))

    def test_add_tag(self):
        """
        Tests the method adding a tag
        """

        # Testing with a first tag
        database = Database(self.string_engine)
        return_value = database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")
        self.assertIsNone(return_value)

        # Checking the tag properties
        tag = database.get_tag("PatientName")
        self.assertEqual(tag.name, "PatientName")
        self.assertEqual(tag.origin, TAG_ORIGIN_BUILTIN)
        self.assertEqual(tag.type, TAG_TYPE_STRING)
        self.assertIsNone(tag.unit)
        self.assertIsNone(tag.default_value)
        self.assertEqual(tag.description, "Name of the patient")

        # Testing with a tag that already exists
        try:
            database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,TAG_TYPE_STRING, None, None, "Name of the patient")
            self.fail()
        except ValueError:
            pass

        # Testing with all tag types
        database.add_tag("BandWidth", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_FLOAT, TAG_UNIT_MHZ, None, None)
        database.add_tag(
            "Bits per voxel", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, "with space")
        database.add_tag(
            "AcquisitionTime", TAG_ORIGIN_BUILTIN, TAG_TYPE_TIME, None, None, None)
        database.add_tag(
            "AcquisitionDate", TAG_ORIGIN_BUILTIN, TAG_TYPE_DATETIME, None, None, None)
        database.add_tag("Dataset dimensions",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, None, None, None)

        database.add_tag(
            "Bitspervoxel", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, "without space")
        self.assertEqual(database.get_tag("Bitspervoxel").description, "without space")
        self.assertEqual(database.get_tag("Bits per voxel").description, "with space")
        database.add_tag("Boolean",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_BOOLEAN, None, None, None)
        database.add_tag("Boolean list",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_BOOLEAN, None, None, None)

        # Testing with wrong parameters
        try:
            database.add_tag(None, TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, None, None, None)
            self.fail()
        except ValueError:
            pass
        try:
            database.add_tag("Patient Name", True, TAG_TYPE_LIST_INTEGER, None, None, None)
            self.fail()
        except ValueError:
            pass
        try:
            database.add_tag("Patient Name", TAG_ORIGIN_BUILTIN, None, None, None, None)
            self.fail()
        except ValueError:
            pass
        try:
            database.add_tag("Patient Name", TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, "unit", None, None)
            self.fail()
        except ValueError:
            pass
        try:
            database.add_tag("Patient Name", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, True, None)
            self.fail()
        except ValueError:
            pass
        try:
            database.add_tag("Patient Name", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, 1.5)
            self.fail()
        except ValueError:
            pass

        # Testing that the tag name is taken for the primary key name column
        try:
            database.add_tag("name", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, None)
            self.fail()
        except ValueError:
            pass

        # TODO Testing tag table or tag column creation

    def test_remove_tag(self):
        """
        Tests the method removing a tag
        """

        database = Database(self.string_engine, True)

        # Adding tags
        return_value = database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")
        self.assertEqual(return_value, None)
        database.add_tag(
            "SequenceName", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, None)
        database.add_tag("Dataset dimensions",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, None, None, None)

        # Adding paths
        database.add_path("path1")
        database.add_path("path2")

        # Adding values
        database.new_value("path1", "PatientName", "Guerbet", "Guerbet_init")
        database.new_value("path1", "SequenceName", "RARE")
        database.new_value("path1", "Dataset dimensions", [1, 2])

        # Removing tag

        database.remove_tag("PatientName")
        database.remove_tag("Dataset dimensions")

        # Testing that the tag does not exist anymore
        self.assertIsNone(database.get_tag("PatientName"))
        self.assertIsNone(database.get_tag("Dataset dimensions"))

        # Testing that the tag values are removed
        self.assertIsNone(database.get_current_value("path1", "PatientName"))
        self.assertIsNone(database.get_initial_value("path1", "PatientName"))
        self.assertEqual(database.get_current_value("path1", "SequenceName"), "RARE")
        self.assertIsNone(database.get_current_value("path1", "Dataset dimensions"))

        # Testing with a tag not existing
        try:
            database.remove_tag("NotExisting")
            self.fail()
        except ValueError:
            pass
        try:
            database.remove_tag("Dataset dimension")
            self.fail()
        except ValueError:
            pass

        # Testing with wrong parameter
        try:
            database.remove_tag(1)
            self.fail()
        except ValueError:
            pass
        try:
            database.remove_tag(None)
            self.fail()
        except ValueError:
            pass

        # TODO Testing tag table or tag column removal

    def test_get_tag(self):
        """
        Tests the method giving the tag row of a tag
        """

        database = Database(self.string_engine)

        # Adding a tag
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")

        # Testing that the tag is returned if it exists
        self.assertIsNotNone(database.get_tag("PatientName"))

        # Testing that None is returned if the tag does not exist
        self.assertIsNone(database.get_tag("Test"))

    def test_get_current_value(self):
        """
        Tests the method giving the current value, given a tag and a path
        """

        database = Database(self.string_engine)

        # Adding paths
        database.add_path("path1")

        # Adding tags
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")
        database.add_tag("Dataset dimensions",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, None, None, None)
        database.add_tag(
            "Bits per voxel", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, None)
        database.add_tag(
            "Grids spacing", TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_FLOAT, None, None, None)

        # Adding values
        database.new_value("path1", "PatientName", "test")
        database.new_value("path1", "Bits per voxel", 10)
        database.new_value(
            "path1", "Dataset dimensions", [3, 28, 28, 3])
        database.new_value("path1", "Grids spacing", [
                           0.234375, 0.234375, 0.4])

        # Testing that the value is returned if it exists
        self.assertEqual(database.get_current_value("path1", "PatientName"), "test")
        self.assertEqual(database.get_current_value("path1", "Bits per voxel"), 10)
        self.assertEqual(database.get_current_value("path1", "Dataset dimensions"), [3, 28, 28, 3])
        self.assertEqual(database.get_current_value("path1", "Grids spacing"), [0.234375, 0.234375, 0.4])

        # Testing when not existing
        self.assertIsNone(database.get_current_value("path3", "PatientName"))
        self.assertIsNone(database.get_current_value("path1", "NotExisting"))
        self.assertIsNone(database.get_current_value("path3", "NotExisting"))
        self.assertIsNone(database.get_current_value("path2", "Grids spacing"))

        # Testing with wrong parameters
        self.assertIsNone(database.get_current_value(1, "Grids spacing"))
        self.assertIsNone(database.get_current_value("path1", None))
        self.assertIsNone(database.get_current_value(3.5, None))

    def test_get_initial_value(self):
        """
        Tests the method giving the initial value, given a tag and a path
        """

        database = Database(self.string_engine, True)

        # Adding paths
        database.add_path("path1")

        # Adding tags
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")
        database.add_tag(
            "Bits per voxel", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, None)
        database.add_tag("Dataset dimensions",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, None, None, None)
        database.add_tag(
            "Grids spacing", TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_FLOAT, None, None, None)

        # Adding values
        database.new_value("path1", "PatientName", "test", "test")
        database.new_value("path1", "Bits per voxel", 50, 50)
        database.new_value(
            "path1", "Dataset dimensions", [3, 28, 28, 3], [3, 28, 28, 3])
        database.new_value("path1", "Grids spacing", [
                           0.234375, 0.234375, 0.4], [0.234375, 0.234375, 0.4])

        # Testing that the value is returned if it exists
        value = database.get_initial_value("path1", "PatientName")
        self.assertEqual(value, "test")
        value = database.get_initial_value("path1", "Bits per voxel")
        self.assertEqual(value, 50)
        value = database.get_initial_value("path1", "Dataset dimensions")
        self.assertEqual(value, [3, 28, 28, 3])
        value = database.get_initial_value("path1", "Grids spacing")
        self.assertEqual(value, [0.234375, 0.234375, 0.4])

        # Testing when not existing
        value = database.get_initial_value("path3", "PatientName")
        self.assertIsNone(value)
        value = database.get_initial_value("path1", "NotExisting")
        self.assertIsNone(value)
        value = database.get_initial_value("path3", "NotExisting")
        self.assertIsNone(value)

        # Testing with wrong parameters
        self.assertIsNone(database.get_initial_value(1, "Grids spacing"))
        self.assertIsNone(database.get_initial_value("path1", None))
        self.assertIsNone(database.get_initial_value(3.5, None))

    def test_is_value_modified(self):
        """
        Tests the method telling if the value has been modified or not
        """

        database = Database(self.string_engine, True)

        # Adding path
        database.add_path("path1")

        # Adding tag
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")

        # Adding a value
        database.new_value("path1", "PatientName", "test", "test")

        # Testing that the value has not been modified
        is_modified = database.is_value_modified("path1", "PatientName")
        self.assertFalse(is_modified)

        # Value modified
        database.set_current_value("path1", "PatientName", "test2")

        # Testing that the value has been modified
        is_modified = database.is_value_modified("path1", "PatientName")
        self.assertTrue(is_modified)

        # Testing with values not existing
        self.assertFalse(database.is_value_modified("path2", "PatientName"))
        self.assertFalse(database.is_value_modified("path1", "NotExisting"))
        self.assertFalse(database.is_value_modified("path2", "NotExisting"))

        # Testing with wrong parameters
        self.assertFalse(database.is_value_modified(1, "Grids spacing"))
        self.assertFalse(database.is_value_modified("path1", None))
        self.assertFalse(database.is_value_modified(3.5, None))

    def test_set_value(self):
        """
        Tests the method setting a value
        """

        database = Database(self.string_engine, True)

        # Adding path
        database.add_path("path1")

        # Adding tags
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")
        database.add_tag(
            "Bits per voxel", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, None)
        database.add_tag(
            "AcquisitionDate", TAG_ORIGIN_BUILTIN, TAG_TYPE_DATETIME, None, None, None)
        database.add_tag(
            "AcquisitionTime", TAG_ORIGIN_BUILTIN, TAG_TYPE_TIME, None, None, None)

        # Adding values and changing it
        database.new_value("path1", "PatientName", "test", "test")
        database.set_current_value("path1", "PatientName", "test2")

        database.new_value("path1", "Bits per voxel", 1, 1)
        database.set_current_value("path1", "Bits per voxel", 2)

        date = datetime.datetime(2014, 2, 11, 8, 5, 7)
        database.new_value("path1", "AcquisitionDate", date, date)
        value = database.get_current_value("path1", "AcquisitionDate")
        self.assertEqual(value, date)
        date = datetime.datetime(2015, 2, 11, 8, 5, 7)
        database.set_current_value("path1", "AcquisitionDate", date)

        time = datetime.datetime(2014, 2, 11, 0, 2, 20).time()
        database.new_value("path1", "AcquisitionTime", time, time)
        self.assertEqual(database.get_current_value("path1", "AcquisitionTime"), time)
        time = datetime.datetime(2014, 2, 11, 15, 24, 20).time()
        database.set_current_value("path1", "AcquisitionTime", time)

        # Testing that the values are actually set
        self.assertEqual(database.get_current_value("path1", "PatientName"), "test2")
        self.assertEqual(database.get_current_value("path1", "Bits per voxel"), 2)
        self.assertEqual(database.get_current_value("path1", "AcquisitionDate"), date)
        self.assertEqual(database.get_current_value("path1", "AcquisitionTime"), time)
        database.set_current_value("path1", "PatientName", None)
        self.assertIsNone(database.get_current_value("path1", "PatientName"))

        # Testing when not existing
        try:
            database.set_current_value("path3", "PatientName", None)
            self.fail()
        except ValueError:
            pass
        try:
            database.set_current_value("path1", "NotExisting", None)
            self.fail()
        except ValueError:
            pass
        try:
            database.set_current_value("path3", "NotExisting", None)
            self.fail()
        except ValueError:
            pass

        # Testing with wrong types
        try:
            database.set_current_value("path1", "Bits per voxel", "test")
            self.fail()
        except ValueError:
            pass
        self.assertEqual(database.get_current_value("path1", "Bits per voxel"), 2)
        try:
            database.set_current_value("path1", "Bits per voxel", 35.8)
            self.fail()
        except ValueError:
            pass
        self.assertEqual(database.get_current_value("path1", "Bits per voxel"), 2)

        # Testing with wrong parameters
        try:
            database.set_current_value(1, "Bits per voxel", "2")
            self.fail()
        except ValueError:
            pass
        try:
            database.set_current_value("path1", None, "1")
            self.fail()
        except ValueError:
            pass
        try:
            database.set_current_value(1, None, True)
            self.fail()
        except ValueError:
            pass

    def test_reset_value(self):
        """
        Tests the method resetting a value
        """

        database = Database(self.string_engine, True)

        # Adding path
        database.add_path("path1")

        # Adding tags
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")
        database.add_tag(
            "Bits per voxel", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, None)
        database.add_tag("Dataset dimensions",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, None, None, None)

        # Adding values and changing it
        database.new_value("path1", "PatientName", "test", "test")
        database.set_current_value("path1", "PatientName", "test2")

        database.new_value("path1", "Bits per voxel", 5, 5)
        database.set_current_value("path1", "Bits per voxel", 15)
        self.assertEqual(database.get_current_value("path1", "Bits per voxel"), 15)

        database.new_value(
            "path1", "Dataset dimensions", [3, 28, 28, 3], [3, 28, 28, 3])
        self.assertEqual(database.get_current_value("path1", "Dataset dimensions"), [3, 28, 28, 3])
        database.set_current_value("path1", "Dataset dimensions", [1, 2, 3, 4])
        self.assertEqual(database.get_current_value("path1", "Dataset dimensions"), [1, 2, 3, 4])

        # Reset of the values
        database.reset_current_value("path1", "PatientName")
        database.reset_current_value("path1", "Bits per voxel")
        database.reset_current_value("path1", "Dataset dimensions")

        # Testing when not existing
        try:
            database.reset_current_value("path3", "PatientName")
            self.fail()
        except ValueError:
            pass
        try:
            database.reset_current_value("path1", "NotExisting")
            self.fail()
        except ValueError:
            pass
        try:
            database.reset_current_value("path3", "NotExisting")
            self.fail()
        except ValueError:
            pass

        # Testing that the values are actually reset
        self.assertEqual(database.get_current_value("path1", "PatientName"), "test")
        self.assertEqual(database.get_current_value("path1", "Bits per voxel"), 5)
        self.assertEqual(database.get_current_value("path1", "Dataset dimensions"), [3, 28, 28, 3])

        # Testing with wrong parameters
        try:
            database.reset_current_value(1, "Bits per voxel")
            self.fail()
        except ValueError:
            pass
        try:
            database.reset_current_value("path1", None)
            self.fail()
        except ValueError:
            pass
        try:
            database.reset_current_value(3.5, None)
            self.fail()
        except ValueError:
            pass

    def test_remove_value(self):
        """
        Tests the method removing a value
        """

        database = Database(self.string_engine, True)

        # Adding path
        database.add_path("path1")

        # Adding tags
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")
        database.add_tag(
            "Bits per voxel", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, None)
        database.add_tag("Dataset dimensions",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, None, None, None)

        # Adding values
        database.new_value("path1", "PatientName", "test")
        try:
            database.new_value("path1", "Bits per voxel", "space_tag")
            self.fail()
        except ValueError:
            pass
        database.new_value(
            "path1", "Dataset dimensions", [3, 28, 28, 3])
        value = database.get_current_value("path1", "Dataset dimensions")
        self.assertEqual(value, [3, 28, 28, 3])

        # Removing values
        database.remove_value("path1", "PatientName")
        database.remove_value("path1", "Bits per voxel")
        database.remove_value("path1", "Dataset dimensions")

        # Testing when not existing
        try:
            database.remove_value("path3", "PatientName")
            self.fail()
        except ValueError:
            pass
        try:
            database.remove_value("path1", "NotExisting")
            self.fail()
        except ValueError:
            pass
        try:
            database.remove_value("path3", "NotExisting")
            self.fail()
        except ValueError:
            pass

        # Testing that the values are actually removed
        self.assertIsNone(database.get_current_value("path1", "PatientName"))
        self.assertIsNone(database.get_current_value("path1", "Bits per voxel"))
        self.assertIsNone(database.get_current_value("path1", "Dataset dimensions"))
        self.assertIsNone(database.get_initial_value("path1", "Dataset dimensions"))

    def test_check_type_value(self):
        """
        Tests the method checking the validity of incoming values
        """

        database = Database(self.string_engine)
        is_valid = database.check_type_value("string", TAG_TYPE_STRING)
        self.assertTrue(is_valid)
        is_valid = database.check_type_value(1, TAG_TYPE_STRING)
        self.assertFalse(is_valid)
        is_valid = database.check_type_value(None, TAG_TYPE_STRING)
        self.assertTrue(is_valid)
        is_valid = database.check_type_value(1, TAG_TYPE_INTEGER)
        self.assertTrue(is_valid)
        is_valid = database.check_type_value(1, TAG_TYPE_FLOAT)
        self.assertTrue(is_valid)
        is_valid = database.check_type_value(1.5, TAG_TYPE_FLOAT)
        self.assertTrue(is_valid)
        is_valid = database.check_type_value(None, None)
        self.assertFalse(is_valid)
        is_valid = database.check_type_value([1.5], TAG_TYPE_LIST_FLOAT)
        self.assertTrue(is_valid)
        is_valid = database.check_type_value(1.5, TAG_TYPE_LIST_FLOAT)
        self.assertFalse(is_valid)
        is_valid = database.check_type_value(
            [1.5, "test"], TAG_TYPE_LIST_FLOAT)
        self.assertFalse(is_valid)

    def test_new_value(self):
        """
        Tests the method adding a value
        """

        database = Database(self.string_engine, True)

        # Adding paths
        database.add_path("path1")
        database.add_path("path2")

        # Adding tags
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")
        database.add_tag(
            "Bits per voxel", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, None)
        database.add_tag(
            "BandWidth", TAG_ORIGIN_BUILTIN, TAG_TYPE_FLOAT, None, None, None)
        database.add_tag(
            "AcquisitionTime", TAG_ORIGIN_BUILTIN, TAG_TYPE_TIME, None, None, None)
        database.add_tag(
            "AcquisitionDate", TAG_ORIGIN_BUILTIN, TAG_TYPE_DATETIME, None, None, None)
        database.add_tag("Dataset dimensions",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_INTEGER, None, None, None)
        database.add_tag(
            "Grids spacing", TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_FLOAT, None, None, None)
        database.add_tag("Boolean",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_BOOLEAN, None, None, None)
        database.add_tag("Boolean list",
                         TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_BOOLEAN, None, None, None)

        # Adding values
        database.new_value("path1", "PatientName", "test", None)
        database.new_value("path2", "BandWidth", 35.5, 35.5)
        database.new_value("path1", "Bits per voxel", 1, 1)
        database.new_value(
            "path1", "Dataset dimensions", [3, 28, 28, 3], [3, 28, 28, 3])
        database.new_value("path2", "Grids spacing", [
                           0.234375, 0.234375, 0.4], [0.234375, 0.234375, 0.4])
        database.new_value("path1", "Boolean", True)

        # Testing when not existing
        try:
            database.new_value("path1", "NotExisting", "none", "none")
            self.fail()
        except ValueError:
            pass
        try:
            database.new_value("path3", "SequenceName", "none", "none")
            self.fail()
        except ValueError:
            pass
        try:
            database.new_value("path3", "NotExisting", "none", "none")
            self.fail()
        except ValueError:
            pass
        self.assertIsNone(database.new_value("path1", "BandWidth", 45, 45))

        date = datetime.datetime(2014, 2, 11, 8, 5, 7)
        database.new_value("path1", "AcquisitionDate", date, date)
        time = datetime.datetime(2014, 2, 11, 0, 2, 2).time()
        database.new_value("path1", "AcquisitionTime", time, time)

        # Testing that the values are actually added
        self.assertEqual(database.get_current_value("path1", "PatientName"), "test")
        self.assertIsNone(database.get_initial_value("path1", "PatientName"))
        self.assertEqual(database.get_current_value("path2", "BandWidth"), 35.5)
        self.assertEqual(database.get_current_value("path1", "Bits per voxel"), 1)
        self.assertEqual(database.get_current_value("path1", "BandWidth"), 45)
        self.assertEqual(database.get_current_value("path1", "AcquisitionDate"), date)
        self.assertEqual(database.get_current_value("path1", "AcquisitionTime"), time)
        self.assertEqual(database.get_current_value("path1", "Dataset dimensions"), [3, 28, 28, 3])
        self.assertEqual(database.get_current_value("path2", "Grids spacing"), [0.234375, 0.234375, 0.4])
        self.assertEqual(database.get_current_value("path1", "Boolean"), True)

        # Test value override
        try:
            database.new_value("path1", "PatientName", "test2", "test2")
            self.fail()
        except ValueError:
            pass
        value = database.get_current_value("path1", "PatientName")
        self.assertEqual(value, "test")

        # Testing with wrong types
        try:
            database.new_value("path2", "Bits per voxel", "space_tag", "space_tag")
            self.fail()
        except ValueError:
            pass
        self.assertIsNone(database.get_current_value("path2", "Bits per voxel"))
        try:
            database.new_value("path2", "Bits per voxel", 35, 35.5)
            self.fail()
        except ValueError:
            pass
        self.assertIsNone(database.get_current_value("path2", "Bits per voxel"))
        try:
            database.new_value("path1", "BandWidth", "test", "test")
            self.fail()
        except ValueError:
            pass
        self.assertEqual(database.get_current_value("path1", "BandWidth"), 45)

        # Testing with wrong parameters
        try:
            database.new_value(1, "Grids spacing", "2", "2")
            self.fail()
        except ValueError:
            pass
        try:
            database.new_value("path1", None, "1", "1")
            self.fail()
        except ValueError:
            pass
        try:
            database.new_value("path1", "PatientName", None, None)
            self.fail()
        except ValueError:
            pass
        self.assertEqual(database.get_current_value("path1", "PatientName"), "test")
        try:
            database.new_value(1, None, True, False)
            self.fail()
        except ValueError:
            pass
        try:
            database.new_value("path2", "Boolean", "boolean")
            self.fail()
        except ValueError:
            pass

    def test_get_path(self):
        """
        Tests the method giving the path row of a path
        """

        database = Database(self.string_engine)

        # Adding path
        database.add_path("path1")

        # Testing that a path is returned if it exists
        self.assertIsInstance(database.get_path("path1").row, database.table_classes[PATH_TABLE])

        # Testing that None is returned if the path does not exist
        self.assertIsNone(database.get_path("path3"))

        # Testing with wrong parameter
        self.assertIsNone(database.get_path(None))
        self.assertIsNone(database.get_path(1))

    def test_remove_path(self):
        """
        Tests the method removing a path
        """
        database = Database(self.string_engine)

        # Adding path
        database.add_path("path1")
        database.add_path("path2")

        # Adding tag
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN,
                         TAG_TYPE_STRING, None, None, "Name of the patient")

        # Adding value
        database.new_value("path1", "PatientName", "test")

        # Removing path
        database.remove_path("path1")

        # Testing that the path is removed from all tables
        self.assertIsNone(database.get_path("path1"))

        # Testing that the values associated are removed
        self.assertIsNone(database.get_current_value("path1", "PatientName"))

        # Testing with a path not existing
        try:
            database.remove_path("NotExisting")
            self.fail()
        except ValueError:
            pass

        # Removing path
        database.remove_path("path2")

        # Testing that the path is removed from all tables
        self.assertIsNone(database.get_path("path2"))

        # Removing path a second time
        try:
            database.remove_path("path1")
            self.fail()
        except ValueError:
            pass

    def test_add_path(self):
        """
        Tests the method adding a path
        """

        database = Database(self.string_engine)

        # Adding path
        database.add_path("path1")

        # Testing that the path has been added
        path = database.get_path("path1")
        self.assertIsInstance(path.row, database.table_classes[PATH_TABLE])
        self.assertEqual(path.name, "path1")

        # Testing when trying to add a path that already exists
        try:
            database.add_path("path1")
            self.fail()
        except ValueError:
            pass

        # Testing with invalid parameters
        try:
            database.add_path(True)
            self.fail()
        except ValueError:
            pass

        # Testing the add of several paths
        database.add_path("path2")

    def test_get_paths_matching_search(self):
        """
        Tests the method returning the list of paths matching the search(str)
        """

        database = Database(self.string_engine, True)

        # Testing with wrong parameters
        return_list = database.get_paths_matching_search(1, [])
        self.assertEqual(return_list, [])
        return_list = database.get_paths_matching_search("search", 1)
        self.assertEqual(return_list, [])
        database.add_path("path1")
        return_list = database.get_paths_matching_search("search", ["tag_not_existing"])
        self.assertEqual(return_list, [])

        database.add_path("path2")
        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, None)
        database.new_value("path1", "PatientName", "Guerbet1", "Guerbet")
        database.new_value("path2", "PatientName", "Guerbet2", "Guerbet")
        self.assertEqual(database.get_paths_matching_search("search", ["PatientName"]), [])
        self.assertEqual(database.get_paths_matching_search("path", ["PatientName", "name"]), ["path1", "path2"])
        self.assertEqual(database.get_paths_matching_search("Guerbet", ["PatientName"]), ["path1", "path2"])
        self.assertEqual(database.get_paths_matching_search("Guerbet1", ["PatientName"]), ["path1"])
        self.assertEqual(database.get_paths_matching_search("Guerbet2", ["PatientName"]), ["path2"])

    def test_get_paths_matching_advanced_search(self):
        """
        Tests the method returning the list of paths matching the advanced search
        """

        database = Database(self.string_engine)

        return_list = database.get_paths_matching_advanced_search([], [], [], [], [], [])
        self.assertEqual(return_list, [])

        # Testing with wrong parameters
        self.assertEqual(database.get_paths_matching_advanced_search(1, [], [], [], [], []), [])
        self.assertEqual(database.get_paths_matching_advanced_search(["AND"], ["PatientName"], ["="], ["Guerbet"], [""], []), [])
        self.assertEqual(database.get_paths_matching_advanced_search([], [["PatientName"]], ["wrong_condition"], ["Guerbet"], [""], []), [])
        self.assertEqual(database.get_paths_matching_advanced_search([], [["PatientName"]], ["wrong_condition"], ["Guerbet"],["wrong_not"], []), [])
        self.assertEqual(database.get_paths_matching_advanced_search([], [["PatientName"]], ["BETWEEN"], ["Guerbet"],["NOT"], []), [])
        self.assertEqual(database.get_paths_matching_advanced_search([], [["PatientName"]], ["BETWEEN"], ["Guerbet"],["NOT"], 1), [])

        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, None)
        database.add_tag("SequenceName", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, None)
        database.add_tag("BandWidth", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, None)
        database.add_path("path1")
        database.add_path("path2")
        database.add_path("path3")
        database.new_value("path1", "PatientName", "Guerbet")
        database.new_value("path2", "SequenceName", "RARE")
        database.new_value("path3", "BandWidth", 50000)
        self.assertEqual(database.get_paths_matching_advanced_search([], [["PatientName"]], ["="], ["Guerbet"], [""], ["path1", "path2", "path3"]), ["path1"])
        return_list = database.get_paths_matching_advanced_search([], [["PatientName"]], ["="], ["Guerbet"], ["NOT"], ["path1", "path2", "path3"])
        self.assertTrue("path2" in return_list)
        self.assertTrue("path3" in return_list)
        self.assertEqual(len(return_list), 2)
        database.new_value("path2", "PatientName", "Guerbet2")
        database.new_value("path3", "PatientName", "Guerbet3")
        return_list = database.get_paths_matching_advanced_search([], [["PatientName"]], ["="], ["Guerbet"], ["NOT"],["path1", "path2", "path3"])
        self.assertTrue("path2" in return_list)
        self.assertTrue("path3" in return_list)
        self.assertEqual(len(return_list), 2)
        self.assertEqual(database.get_paths_matching_advanced_search([], [["TagNotExisting"]], ["="], ["Guerbet"], [""], ["path1", "path2", "path3"]), [])
        return_list = database.get_paths_matching_advanced_search([], [["name"]], ["CONTAINS"], ["path"], [""], ["path1", "path2", "path3"])
        self.assertTrue("path1" in return_list)
        self.assertTrue("path2" in return_list)
        self.assertTrue("path3" in return_list)
        self.assertEqual(len(return_list), 3)
        return_list = database.get_paths_matching_advanced_search(["OR"], [["PatientName"], ["SequenceName"]], ["=", "CONTAINS"], ["Guerbet", "RARE"], ["", ""], ["path1", "path2", "path3"])
        self.assertTrue("path1" in return_list)
        self.assertTrue("path2" in return_list)
        self.assertEqual(len(return_list), 2)
        self.assertEqual(database.get_paths_matching_advanced_search(["AND"], [["PatientName"], ["SequenceName"]],
                                                                  ["=", "CONTAINS"], ["Guerbet", "RARE"], ["", ""], ["path1", "path2", "path3"]), [])
        self.assertEqual(database.get_paths_matching_advanced_search([], [["BandWidth"]], ["="], ["50000"], [""], ["path1", "path2", "path3"]), ["path3"])
        self.assertEqual(database.get_paths_matching_advanced_search([], [["BandWidth"]], ["="], [50000], [""], ["path1", "path2", "path3"]), [])
        self.assertEqual(database.get_paths_matching_advanced_search([], [["BandWidth"]], ["="], [50000], [""],
                                                                  ["path1", "path2"]), [])

    def test_get_paths_matching_tag_value_couples(self):
        """
        Tests the method giving the list of paths having all the values given
        """

        database = Database(self.string_engine)

        # Testing with wrong parameters
        self.assertEqual(database.get_paths_matching_tag_value_couples([]), [])
        self.assertEqual(database.get_paths_matching_tag_value_couples(False), [])
        self.assertEqual(database.get_paths_matching_tag_value_couples([["tag_not_existing", "Guerbet"]]), [])
        self.assertEqual(database.get_paths_matching_tag_value_couples([["tag_not_existing"]]), [])
        self.assertEqual(database.get_paths_matching_tag_value_couples([["tag_not_existing", "Guerbet", "too_many"]]), [])
        self.assertEqual(database.get_paths_matching_tag_value_couples([1]), [])
        self.assertEqual(database.get_paths_matching_tag_value_couples("test"), [])

        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, None)
        database.add_tag("SequenceName", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, None)
        database.add_tag("BandWidth", TAG_ORIGIN_BUILTIN, TAG_TYPE_INTEGER, None, None, None)
        database.add_path("path1")
        database.add_path("path2")
        database.add_path("path3")
        database.new_value("path1", "PatientName", "Guerbet")
        database.new_value("path2", "SequenceName", "RARE")
        database.new_value("path2", "BandWidth", 50000)

        self.assertEqual(database.get_paths_matching_tag_value_couples([["PatientName", "Guerbet"]]), ["path1"])
        self.assertEqual(database.get_paths_matching_tag_value_couples([["PatientName", "Guerbet"], ["SequenceName", "RARE"]]), [])
        database.new_value("path2", "PatientName", "Guerbet")
        self.assertEqual(database.get_paths_matching_tag_value_couples([["PatientName", "Guerbet"], ["SequenceName", "RARE"]]), ["path2"])
        self.assertEqual(database.get_paths_matching_tag_value_couples(
            [["PatientName", "Guerbet"], ["SequenceName", "RARE"], ["BandWidth", 50000]]), ["path2"])
        self.assertEqual(database.get_paths_matching_tag_value_couples(
            [["PatientName", "Guerbet"], ["SequenceName", "RARE"], ["BandWidth", "50000"]]), [])

    def test_initial_table(self):
        """
        Tests the initial table good behavior
        """

        database = Database(self.string_engine)

        database.add_tag("PatientName", TAG_ORIGIN_BUILTIN, TAG_TYPE_STRING, None, None, None)

        database.add_path("path1")

        database.new_value("path1", "PatientName", "Guerbet")

        # Testing that the value can be set
        self.assertEqual(database.get_current_value("path1", "PatientName"), "Guerbet")
        database.set_current_value("path1", "PatientName", "Guerbet2")
        self.assertEqual(database.get_current_value("path1", "PatientName"), "Guerbet2")

        # Testing that the values cannot be reset
        try:
            database.reset_current_value("path1", "PatientName")
            self.fail()
        except ValueError:
            pass

        database.remove_value("path1", "PatientName")

        # Testing that initial cannot be added if the flag initial_table is put to False
        try:
            database.new_value("path1", "PatientName", "Guerbet_current", "Guerbet_initial")
            self.fail()
        except ValueError:
            pass

        # Testing that initial paths do not exist
        try:
            database.get_initial_path("path1")
            self.fail()
        except ValueError:
            pass

        database.save_modifications()

        # Testing that the flag cannot be True if the database already exists without the initial table
        try:
            database = Database(self.string_engine, True)
            self.fail()
        except ValueError:
            pass

    def test_list_dates(self):
        """
        Tests the storage and retrieval of tags of type list of time, date
        and datetime
        """

        database = Database(self.string_engine)

        database.add_tag("list_date", TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_DATE, None, None, None)
        database.add_tag("list_time", TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_TIME, None, None, None)
        database.add_tag("list_datetime", TAG_ORIGIN_BUILTIN, TAG_TYPE_LIST_DATETIME, None, None, None)
        
        database.add_path("path1")

        list_date = [datetime.date(2018, 5, 23), datetime.date(1899, 12, 31)]
        list_time = [datetime.time(12, 41, 33, 540), datetime.time(1, 2, 3)]
        list_datetime = [datetime.datetime(2018, 5, 23, 12, 41, 33, 540), 
                         datetime.datetime(1899, 12, 31, 1, 2, 3)]
        
        database.new_value("path1", "list_date", list_date)
        self.assertEqual(list_date, database.get_current_value("path1", "list_date"))
        database.new_value("path1", "list_time", list_time)
        self.assertEqual(list_time, database.get_current_value("path1", "list_time"))
        database.new_value("path1", "list_datetime", list_datetime)
        self.assertEqual(list_datetime, database.get_current_value("path1", "list_datetime"))

    def test_filters(self):
        database = Database(self.string_engine)
        
        database.add_tag('format', tag_type='string', origin=TAG_ORIGIN_BUILTIN,
                unit=None, description=None, default_value=None)
        database.add_tag('strings', tag_type=TAG_TYPE_LIST_STRING, origin=TAG_ORIGIN_BUILTIN,
                unit=None, description=None, default_value=None)
        database.add_tag('times', tag_type=TAG_TYPE_LIST_TIME, origin=TAG_ORIGIN_BUILTIN,
                unit=None, description=None, default_value=None)
        database.add_tag('dates', tag_type=TAG_TYPE_LIST_DATE, origin=TAG_ORIGIN_BUILTIN,
                unit=None, description=None, default_value=None)
        database.add_tag('datetimes', tag_type=TAG_TYPE_LIST_DATETIME, origin=TAG_ORIGIN_BUILTIN,
                unit=None, description=None, default_value=None)

        database.save_modifications()
        files = ('abc', 'bcd', 'def', 'xyz')
        for file in files:
            for format, ext in (('NIFTI', 'nii'), 
                                ('DICOM', 'dcm'),
                                ('Freesurfer', 'mgz')):
                path = '/%s.%s' % (file, ext    )
                database.add_path(path)
                database.new_value(path, 'format', format)
                database.new_value(path, 'strings', list(file))

        for filter, expected in (
            ('format == "NIFTI"', set('/%s.nii' %i for i in files)),
            ('"b" IN strings', {'/abc.nii',
                                '/abc.mgz',
                                '/abc.dcm',
                                '/bcd.nii',
                                '/bcd.dcm',
                                '/bcd.mgz'}
            ),
            ('(format == "NIFTI" OR NOT format == "DICOM") AND ("a" IN strings OR NOT "b" IN strings)',
             {'/xyz.nii',
              '/abc.nii',
              '/abc.mgz',
              '/xyz.mgz',
              '/def.mgz',
              '/def.nii'}
            )):
            paths = set(path.name for path in database.filter_paths(filter))
            self.assertEqual(paths, expected)

            
if __name__ == '__main__':
    unittest.main()