import ast
import copy
import hashlib
import os
import re
import types
from datetime import date, time, datetime

import dateutil.parser
import six
from sqlalchemy import (create_engine, Column, String,
                        MetaData, event, Table, sql)
from sqlalchemy.engine import Engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker, scoped_session, mapper
from sqlalchemy.schema import CreateTable, DropTable

from populse_db.database_model import (create_database, FIELD_TYPE_INTEGER,
                                       FIELD_TYPE_FLOAT, FIELD_TYPE_TIME,
                                       FIELD_TYPE_DATETIME, FIELD_TYPE_DATE,
                                       FIELD_TYPE_STRING, FIELD_TYPE_LIST_DATE,
                                       FIELD_TYPE_LIST_DATETIME,LIST_TYPES,
                                       FIELD_TYPE_LIST_TIME, ALL_TYPES,
                                       TYPE_TO_COLUMN, FIELD_TYPE_BOOLEAN,
                                       FIELD_TABLE, COLLECTION_TABLE)

from populse_db.filter import filter_parser, FilterToQuery


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Manages the pragmas during the database opening
    :param dbapi_connection:
    :param connection_record:
    """
    dbapi_connection.execute('pragma case_sensitive_like=ON')
    dbapi_connection.execute('pragma foreign_keys=ON')


class Database:

    """
    Database API

    attributes:
        - string_engine: string engine of the database
        - table_classes: list of table classes, generated automatically
        - base: database base
        - engine: database engine
        - metadata: database metadata
        - session_maker: session manager
        - unsaved_modifications: bool to know if there are unsaved
          modifications in the database
        - documents: document rows
        - fields: fields rows
        - names: fields column names
        - collections: collections rows

    methods:
        - add_collection: adds a collection
        - get_collection: gives the collection row
        - add_field: adds a field
        - add_fields: adds a list of fields
        - field_type_to_column_type: gives the column type corresponding
          to a field type
        - field_name_to_column_name: gives the column name corresponding
          to the field name
        - remove_field: removes a field
        - get_field: Gives all fields rows
        - get_fields_names: gives all fields names
        - get_documents: gives all document rows
        - get_documents_names: gives all document names
        - get_value: gives the value of <document, field>
        - set_value: sets the value of <document, field>
        - remove_value: removes the value of <document, field>
        - check_type_value: checks the type of a value
        - add_value: adds a value to <document, field>
        - get_document: gives the document row given a document name
        - get_documents: gives all document rows
        - get_documents_names: gives all document names
        - add_document: adds a document
        - remove_document: removes a document
        - get_documents_matching_constraints: gives the documents matching the
          constraints given in parameter
        - get_documents_matching_search: gives the documents matching the
          search
        - get_documents_matching_advanced_search: gives the documents matching
          the advanced search
        - get_documents_matching_field_value_couples: gives the documents
          containing all <field, value> given in parameter
        - save_modifications: saves the pending modifications
        - unsave_modifications: unsaves the pending modifications
        - has_unsaved_modifications: to know if there are unsaved
          modifications
        - update_table_classes: redefines the model after schema update
    """

    # Some types (e.g. time, date and datetime) cannot be
    # serialized/deserialized into string with repr/ast.literal_eval.
    # This is a problem for storing the corresponding list_columns in
    # database. For the list types with this problem, we record in the
    # following dictionaries the functions that must be used to serialize
    # (in _list_item_to_string) and deserialize (in _string_to_list_item)
    # the list items.
    _list_item_to_string = {
        FIELD_TYPE_LIST_DATE: lambda x: x.isoformat(),
        FIELD_TYPE_LIST_DATETIME: lambda x: x.isoformat(),
        FIELD_TYPE_LIST_TIME: lambda x: x.isoformat()
    }

    _string_to_list_item = {
        FIELD_TYPE_LIST_DATE: lambda x: dateutil.parser.parse(x).date(),
        FIELD_TYPE_LIST_DATETIME: lambda x: dateutil.parser.parse(x),
        FIELD_TYPE_LIST_TIME: lambda x: dateutil.parser.parse(x).time(),
    }

    def __init__(self, string_engine, caches=False):
        """
        Creates an API of the database instance
        :param string_engine: string engine of the database file, can be already existing, or not
        :param caches: to know if the caches must be used, False by default
        """

        self.string_engine = string_engine

        self.caches = caches

        # SQLite database: we create it if it does not exist
        if string_engine.startswith('sqlite'):
            self.db_file = re.sub("sqlite.*:///", "", string_engine)
            if not os.path.exists(self.db_file):
                parent_dir = os.path.dirname(self.db_file)
                if not os.path.exists(parent_dir):
                    os.makedirs(os.path.dirname(self.db_file))
                create_database(string_engine)

        # Database opened
        self.engine = create_engine(self.string_engine)
        self.metadata = MetaData()
        self.metadata.reflect(self.engine)
        self.update_table_classes()

        # Database schema checked
        if (COLLECTION_TABLE not in self.table_classes.keys() or
                FIELD_TABLE not in self.table_classes.keys()):
            raise ValueError(
                'The database schema is not coherent with the API')

        self.session = scoped_session(sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False))

        self.unsaved_modifications = False

        if self.caches:
            self.documents = {}
            self.fields = {}
            self.names = {}
            self.collections = {}

    """ COLLECTIONS """

    def add_collection(self, name, primary_key="name"):
        """
        Adds a collection
        :param name: New collection name
        :param primary_key: New collection primary_key column
        """

        # Checks that the collection does not already exist
        collection_row = self.get_collection(name)
        if collection_row is not None or name in self.table_classes:
            raise ValueError("A collection/table with the name " +
                             str(name) + " already exists")

        # Adding the collection row
        collection_row = self.table_classes[COLLECTION_TABLE](name=name, primary_key=primary_key)
        self.session.add(collection_row)

        # Creating the collection document table
        collection_table = Table(name, self.metadata, Column(primary_key, String, primary_key=True))
        collection_query = CreateTable(collection_table)
        self.session.execute(collection_query)

        # Creating the class associated
        collection_dict = {'__tablename__': name, '__table__': collection_table}
        collection_class = type(name, (self.base,), collection_dict)
        mapper(collection_class, collection_table)
        self.table_classes[name] = collection_class

        # Adding the primary_key of the collection as field
        field_table = self.metadata.tables[FIELD_TABLE]
        insert = field_table.insert().values(name=primary_key, collection=name,
                                             type=FIELD_TYPE_STRING, description="Primary_key of the document collection " + name)
        self.session.execute(insert)

        if self.caches:
            self.documents[name] = {}
            self.fields[name] = {}
            self.names[name] = {}
            self.collections[name] = collection_row

        self.session.flush()

    def get_collection(self, name):
        """
        Returns the collection row of the collection
        :param name: collection name
        :return: The collection row if it exists, None otherwise
        """

        if self.caches:
            try:
                return self.collections[name]
            except KeyError:
                collection_row = self.session.query(self.table_classes[COLLECTION_TABLE]).filter(
                    self.table_classes[COLLECTION_TABLE].name == name).first()
                self.collections[name] = collection_row
                return collection_row
        else:
            collection_row = self.session.query(self.table_classes[COLLECTION_TABLE]).filter(self.table_classes[COLLECTION_TABLE].name == name).first()
            return collection_row

    """ FIELDS """

    def add_fields(self, fields):
        """
        Adds the list of fields
        :param fields: list of fields (collection, name, type, description)
        """

        for field in fields:

            # Adding each field
            self.add_field(field[0], field[1], field[2], field[3], False)

        # Updating the table classes
        self.session.flush()
        self.update_table_classes()

    def add_field(self, collection, name, field_type, description, flush=True):
        """
        Adds a field to the database, if it does not already exist
        :param collection: field collection (str)
        :param name: field name (str)
        :param field_type: field type (string, int, float, boolean, date, datetime,
                     time, list_string, list_int, list_float, list_boolean, list_date,
                     list_datetime, or list_time)
        :param description: field description (str or None)
        :param flush: bool to know if the table classes must be updated (put False if in the middle of filling fields)
        """

        if not isinstance(name, str):
            raise ValueError("The field name must be of type " + str(str) +
                             ", but field name of type " + str(type(name)) + " given")
        if not isinstance(collection, str):
            raise ValueError("The collection name must be of type " + str(str) +
                             ", but collection name of type " + str(type(collection)) + " given")
        collection_row = self.get_collection(collection)
        if collection_row is None:
            raise ValueError("The collection " +
                             str(collection) + " does not exist")
        field_row = self.get_field(collection, name)
        if field_row is not None:
            raise ValueError("A field with the name " +
                             str(name) + " already exists in the collection " + collection)
        if not field_type in ALL_TYPES:
            raise ValueError("The field type must be in " + str(ALL_TYPES) + ", but " + str(
                field_type) + " given")
        if not isinstance(description, str) and description is not None:
            raise ValueError(
                "The field description must be of type " + str(str) + " or None, but field description of type " + str(
                    type(description)) + " given")

        # Adding the field in the field table
        field_row = self.table_classes[FIELD_TABLE](name=name, collection=collection, type=field_type, description=description)
        if self.caches:
            self.fields[collection][name] = field_row
        self.session.add(field_row)

        # Fields creation
        if field_type in LIST_TYPES:
            # String columns if it list type, as the str representation of the lists will be stored
            field_type = String
        else:
            field_type = self.field_type_to_column_type(field_type)
        column = Column(self.field_name_to_column_name(collection, name), field_type)
        column_str_type = column.type.compile(self.engine.dialect)
        column_name = column.compile(dialect=self.engine.dialect)

        # Column created in document table, and in initial table if initial values are used

        document_query = str('ALTER TABLE %s ADD COLUMN %s %s' %
                         (collection, column_name, column_str_type))
        self.session.execute(document_query)
        self.table_classes[collection].__table__.append_column(column)

        if self.caches:
            for collection in self.documents:
                self.documents[collection] = {}

        self.unsaved_modifications = True

        # Redefinition of the table classes
        if flush:
            self.session.flush()
            self.update_table_classes()

    def field_type_to_column_type(self, field_type):
        """
        Gives the sqlalchemy column type corresponding to the field type
        :param field_type: column type
        :return: The sql column type given the field type
        """

        return TYPE_TO_COLUMN[field_type]

    def field_name_to_column_name(self, collection, field):
        """
        Transforms the field name into a valid and unique column name, by hashing it
        :param collection: field collection (str)
        :param field: field name (str)
        :return: Valid and unique (hashed) column name
        """

        collection_row = self.get_collection(collection)
        if collection_row is None:
            return None
        else:
            primary_key = collection_row.primary_key
            if self.caches:
                try:
                    return self.names[collection][field]
                except KeyError:
                    if field == primary_key:
                        try:
                            self.names[collection][field] = field
                            return field
                        except KeyError:
                            self.names[collection] = {}
                            self.names[collection][field] = field
                            return field
                    else:
                        new_name = hashlib.md5(field.encode('utf-8')).hexdigest()
                        try:
                            self.names[collection][field] = new_name
                        except KeyError:
                            self.names[collection] = {}
                            self.names[collection][field] = new_name
                        return new_name
            else:
                if field == primary_key:
                    return field
                else:
                    field_name = hashlib.md5(field.encode('utf-8')).hexdigest()
                    return field_name

    def remove_field(self, collection, field):
        """
        Removes a field in the collection
        :param collection: field collection
        :param field: field name (str)
        """

        if not isinstance(field, str):
            raise ValueError(
                "The field name must be of type " + str(str) + ", but field name of type " + str(type(field)) + " given")
        if not isinstance(collection, str):
            raise ValueError(
                "The collection must be of type " + str(str) + ", but collection of type " + str(type(collection)) + " given")
        collection_row = self.get_collection(collection)
        if collection_row is None:
            raise ValueError("The collection " +
                             str(collection) + " does not exist")
        field_row = self.get_field(collection, field)
        if field_row is None:
            raise ValueError("The field with the name " +
                             str(field) + " does not exist in the collection " + collection)

        field_name = self.field_name_to_column_name(collection, field)
        primary_key = self.get_collection(collection).primary_key

        # Field removed from document table
        old_document_table = Table(collection, self.metadata)
        select = sql.select(
            [c for c in old_document_table.c if field_name not in c.name])

        remaining_columns = [copy.copy(c) for c in old_document_table.columns
                             if field_name not in c.name]

        document_backup_table = Table(collection + "_backup", self.metadata)
        for column in old_document_table.columns:
            if field_name not in str(column):
                document_backup_table.append_column(column.copy())
        self.session.execute(CreateTable(document_backup_table))

        insert = sql.insert(document_backup_table).from_select(
            [c.name for c in remaining_columns], select)
        self.session.execute(insert)

        self.metadata.remove(old_document_table)
        self.session.execute(DropTable(old_document_table))

        new_document_table = Table(collection, self.metadata)
        for column in document_backup_table.columns:
            new_document_table.append_column(column.copy())

        self.session.execute(CreateTable(new_document_table))

        select = sql.select(
            [c for c in document_backup_table.c if field_name not in c.name])
        insert = sql.insert(new_document_table).from_select(
            [c.name for c in remaining_columns], select)
        self.session.execute(insert)

        self.session.execute(DropTable(document_backup_table))

        if self.caches:
            for collection_name in self.documents:
                self.documents[collection_name] = {}

            self.fields[collection].pop(field, None)

        self.session.delete(field_row)

        self.session.flush()

        self.update_table_classes()

        self.unsaved_modifications = True

    def get_field(self, collection, name):
        """
        Gives the column row given a column name and a collection
        :param collection: document collection
        :param name: column name
        :return: The column row if the column exists, None otherwise
        """

        if self.caches:
            try:
                field_row = self.fields[collection][name]
                return field_row
            except KeyError:
                field_row = self.session.query(self.table_classes[FIELD_TABLE]).filter(
                    self.table_classes[FIELD_TABLE].name == name).filter(
                    self.table_classes[FIELD_TABLE].collection == collection).first()
                collection_row = self.get_collection(collection)
                if collection_row is not None:
                    try:
                        self.fields[collection][name] = field_row
                    except KeyError:
                        self.fields[collection] = {}
                        self.fields[collection][name] = field_row
                    return field_row
                else:
                    return None
        else:
            field_row = self.session.query(self.table_classes[FIELD_TABLE]).filter(self.table_classes[FIELD_TABLE].name == name).filter(self.table_classes[FIELD_TABLE].collection == collection).first()
            return field_row

    def get_fields_names(self, collection):
        """
        Gives the list of fields, given a collection
        :param collection: fields collection
        :return: List of fields names of the collection
        """

        fields = self.session.query(self.table_classes[FIELD_TABLE].name).filter(
            self.table_classes[FIELD_TABLE].collection == collection).all()

        fields_names = []
        for field in fields:
            fields_names.append(field.name)

        return fields_names

    def get_fields(self, collection):
        """
        Gives the list of fields rows, given a collection
        :param collection: fields collection
        :return: List of fields rows of the colletion
        """

        fields = self.session.query(self.table_classes[FIELD_TABLE]).filter(
            self.table_classes[FIELD_TABLE].collection == collection).all()
        return fields

    """ VALUES """

    def get_value(self, collection, document, field):
        """
        Gives the current value of <document, field> in the collection
        :param collection: Document collection (str)
        :param document: Document name (str)
        :param field: Field name (str)
        :return: The current value of <document, field> in the collection if it exists, None otherwise
        """

        collection_row = self.get_collection(collection)
        if collection_row is None:
            return None
        field_row = self.get_field(collection, field)
        if field_row is None:
            return None
        document_row = self.get_document(collection, document)
        if document_row is None:
            return None

        return FieldRow(self, collection, document_row)[field]

    def set_value(self, collection, document, field, new_value, flush=False):
        """
        Sets the value associated to <document, column>
        :param collection: document collection (str)
        :param document: document name (str)
        :param field: Field name (str)
        :param new_value: new value
        :param flush: bool to know if flush to do
        """

        collection_row = self.get_collection(collection)
        if collection_row is None:
            raise ValueError("The collection " + str(collection) + " does not exist")
        field_row = self.get_field(collection, field)
        if field_row is None:
            raise ValueError("The field with the name " +
                             str(field) + " does not exist for the collection " + collection)
        document_row = self.get_document(collection, document)
        if document_row is None:
            raise ValueError("The document with the name " +
                             str(document) + " does not exist")
        if not self.check_type_value(new_value, field_row.type):
            raise ValueError("The value " + str(new_value) + " is invalid")

        new_value = self.python_to_column(field_row.type, new_value)

        setattr(document_row.row, self.field_name_to_column_name(collection, field), new_value)

        if flush:
            self.session.flush()

        self.unsaved_modifications = True

    def remove_value(self, collection, document, field, flush=True):
        """
        Removes the value associated to <document, field> in the collection
        :param collection: document collection (str)
        :param document: document name (str)
        :param field: Field name (str)
        :param flush: To know if flush to do (put False in the middle of removing values)
        """

        collection_row = self.get_collection(collection)
        if collection_row is None:
            raise ValueError("The collection " + str(collection) + " does not exist")
        field_row = self.get_field(collection, field)
        if field_row is None:
            raise ValueError("The field with the name " +
                             str(field) + " does not exist in the collection " + collection)
        document_row = self.get_document(collection, document)
        if document_row is None:
            raise ValueError("The document with the name " +
                             str(document) + " does not exist in the collection " + collection)

        sql_column_name = self.field_name_to_column_name(collection, field)

        setattr(document_row.row, sql_column_name, None)

        if flush:
            self.session.flush()
        self.unsaved_modifications = True

    def check_type_value(self, value, valid_type):
        """
        Checks the type of the value
        :param value: value
        :param type: type that the value is supposed to have
        :return: True if the value is valid, False otherwise
        """

        value_type = type(value)
        if valid_type is None:
            return False
        if value is None:
            return True
        if valid_type == FIELD_TYPE_INTEGER and value_type == int:
            return True
        if valid_type == FIELD_TYPE_FLOAT and value_type == int:
            return True
        if valid_type == FIELD_TYPE_FLOAT and value_type == float:
            return True
        if valid_type == FIELD_TYPE_BOOLEAN and value_type == bool:
            return True
        if valid_type == FIELD_TYPE_STRING and value_type == str:
            return True
        if valid_type == FIELD_TYPE_DATETIME and value_type == datetime:
            return True
        if valid_type == FIELD_TYPE_TIME and value_type == time:
            return True
        if valid_type == FIELD_TYPE_DATE and value_type == date:
            return True
        if (valid_type in LIST_TYPES
                and value_type == list):
            for value_element in value:
                if not self.check_type_value(value_element, valid_type.replace("list_", "")):
                    return False
            return True
        return False

    def new_value(self, collection, document, field, value, checks=True):
        """
        Adds a value for <document, field>
        :param collection: document collection
        :param document: document name
        :param field: Field name
        :param current_value: current value
        :param initial_value: initial value (initial values must be activated)
        :param checks: bool to know if flush to do and value check (Put False in the middle of adding values, during import)
        """

        collection_row = self.get_collection(collection)
        field_row = self.get_field(collection, field)
        document_row = self.get_document(collection, document)

        if checks:
            if collection_row is None:
                raise ValueError("The collection " + str(collection) + " does not exist")
            if field_row is None:
                raise ValueError("The field with the name " +
                                 str(field) + " does not exist in the collection " + collection)
            if document_row is None:
                raise ValueError("The document with the name " +
                                 str(document) + " does not exist in the collection " + collection)
            if not self.check_type_value(value, field_row.type):
                raise ValueError("The value " +
                                 str(value) + " is invalget_cuid")

        field_name = self.field_name_to_column_name(collection, field)
        database_value = getattr(
            document_row, field_name)

        # We add the value only if it does not already exist
        if database_value is None:
            if value is not None:
                current_value = self.python_to_column(
                    field_row.type, value)
                setattr(
                    document_row.row, field_name,
                    current_value)

            if checks:
                self.session.flush()
            self.unsaved_modifications = True

        else:
            raise ValueError("The tuple <" + str(field) + ", " +
                             str(document) + "> already has a value for the collection " + collection)

    """ DOCUMENTS """

    def get_document(self, collection, document):
        """
        Gives the document row of a document, given a collection
        :param collection: document collection
        :param document: document name
        :return The document row if the document exists, None otherwise
        """

        if self.caches:
            try:
                return self.documents[collection][document]
            except KeyError:
                collection_row = self.get_collection(collection)
                if collection_row is None:
                    return None
                else:
                    primary_key = collection_row.primary_key
                    document_row = self.session.query(self.table_classes[collection]).filter(
                        getattr(self.table_classes[collection], primary_key) == document).first()
                    if document_row is not None:
                        document_row = FieldRow(self, collection, document_row)
                    if not collection in self.documents:
                        self.documents[collection] = {}
                    self.documents[collection][document] = document_row
                    return document_row
        else:
            collection_row = self.get_collection(collection)
            if collection_row is None:
                return None
            else:
                primary_key = collection_row.primary_key
                document_row = self.session.query(self.table_classes[collection]).filter(
                    getattr(self.table_classes[collection], primary_key) == document).first()
                if document_row is not None:
                    document_row = FieldRow(self, collection, document_row)
                return document_row

    def get_documents_names(self, collection):
        """
        Gives the list of document names, given a collection
        :param collection: documents collection
        :return: list of document names of the collection
        """

        collection_row = self.get_collection(collection)
        if collection_row is None:
            return []
        else:
            documents_list = []
            documents = self.session.query(getattr(self.table_classes[collection], collection_row.primary_key)).all()
            for document in documents:
                documents_list.append(getattr(document, collection_row.primary_key))
            return documents_list

    def get_documents(self, collection):
        """
        Gives the list of document rows, given a collection
        :param collection: documents collection
        :return: list of document rows of the collection
        """

        collection_row = self.get_collection(collection)
        if collection_row is None:
            return []
        else:
            documents_list = []
            documents = self.session.query(self.table_classes[collection]).all()
            for document in documents:
                documents_list.append(FieldRow(self, collection, document))
            return documents_list

    def remove_document(self, collection, document):
        """
        Removes a document in the collection
        :param collection: document collection (str)
        :param document: document name (str)
        """

        collection_row = self.get_collection(collection)
        if collection_row is None:
            raise ValueError("The collection " + str(collection) + " does not exist")
        document_row = self.get_document(collection, document)
        if document_row is None:
            raise ValueError("The document with the name " +
                             str(document) + " does not exist in the collection " + collection)
        primary_key = collection_row.primary_key

        self.session.query(self.table_classes[collection]).filter(
                getattr(self.table_classes[collection], primary_key) == document).delete()

        if self.caches:
            self.documents[collection][document] = None

        self.session.flush()
        self.unsaved_modifications = True

    def add_document(self, collection, document, checks=True):
        """
        Adds a document to a collection
        :param collection: document collection (str)
        :param document: dictionary of document values, or document name (str)
        :param checks: checks if the document already exists and flushes, put False in the middle of filling the table
        """

        if checks:
            if not isinstance(collection, str):
                raise ValueError(
                    "The collection must be of type " + str(str) + ", but collection of type " + str(
                        type(collection)) + " given")
            collection_row = self.get_collection(collection)
            if collection_row is None:
                raise ValueError("The collection " +
                                 str(collection) + " does not exist")
            primary_key = self.get_collection(collection).primary_key
            if not isinstance(document, dict) and not isinstance(document, str):
                raise ValueError(
                    "The document must be of type " + str(dict) + " or " + str(str) + ", but document of type " + str(
                        type(document)) + " given")
            if isinstance(document, dict):
                document_row = self.get_document(collection, document[primary_key])
            else:
                document_row = self.get_document(collection, document)
            if document_row is not None:
                raise ValueError("A document with the name " +
                                 str(document) + " already exists")
        else:
            primary_key = self.get_collection(collection).primary_key

        # Putting valid columns names in the dictionary
        if isinstance(document, dict):
            new_dict = {}
            for value in document:
                new_column = self.field_name_to_column_name(collection, value)
                new_dict[new_column] = document[value]
                field_row = self.get_field(collection, value)
                new_dict[new_column] = self.python_to_column(field_row.type, new_dict[new_column])
            document = new_dict

        # Adding the index to document table
        if isinstance(document, dict):
            document_row = self.table_classes[collection](**document)
        else:
            args = {}
            args[primary_key] = document
            document_row = self.table_classes[collection](**args)
        self.session.add(document_row)

        if self.caches:
            document_row = FieldRow(self, collection, document_row)
            if isinstance(document, str):
                self.documents[collection][document] = document_row
            else:
                self.documents[collection][document[primary_key]] = document_row

        if checks:
            self.session.flush()

        self.unsaved_modifications = True

    """ UTILS """

    def start_transaction(self):
        """
        Starts a new transaction
        """

        self.session.begin_nested()

    def save_modifications(self):
        """
        Saves the modifications by committing the session
        """

        self.session.commit()
        self.unsaved_modifications = False

    def unsave_modifications(self):
        """
        Unsaves the modifications by rolling back the session
        """

        self.session.rollback()
        self.unsaved_modifications = False

    def has_unsaved_modifications(self):
        """
        Knowing if the database has pending modifications that are
        unsaved
        :return: True if there are pending modifications to save,
                 False otherwise
        """

        return self.unsaved_modifications

    def update_table_classes(self):
        """
        Redefines the model after an update of the schema
        """

        self.table_classes = {}
        self.base = automap_base(metadata=self.metadata)
        self.base.prepare(engine=self.engine)

        for table in self.metadata.tables.values():
            self.table_classes[table.name] = getattr(
                self.base.classes, table.name)

    def filter_query(self, filter, collection):
        """
        Given a filter string, return a query that can be used with
        filter_documents() to select documents.
        """

        tree = filter_parser().parse(filter)
        query = FilterToQuery(self, collection).transform(tree)
        return query

    def filter_documents(self, collection, filter_query):
        """
        Iterate over documents selected by filter_query. Each item yield is a
        row of the column table returned by sqlalchemy. filter_query can be
        the result of self.filter_query() or a string containing a filter
        (in this case self.fliter_query() is called to get the actual query).
        """

        if isinstance(filter_query, six.string_types):
            filter_query = self.filter_query(filter_query, collection)
        if filter_query is None:
            select = self.metadata.tables[collection].select()
            python_filter = None
        elif isinstance(filter_query, types.FunctionType):
            select = self.metadata.tables[collection].select()
            python_filter = filter_query
        elif isinstance(filter_query, tuple):
            sql_condition, python_filter = filter_query
            select = select = self.metadata.tables[collection].select(
                sql_condition)
        else:
            select = select = self.metadata.tables[collection].select(
                filter_query)
            python_filter = None
        for row in self.session.execute(select):
            row = FieldRow(self, collection, row)
            if python_filter is None or python_filter(row):
                yield row

    def python_to_column(self, column_type, value):
        """
        Convert a python value into a suitable value to put in a
        database column.
        """
        if isinstance(value, list):
            return self.list_to_column(column_type, value)
        else:
            return value

    def column_to_python(self, column_type, value):
        """
        Convert a value of a database column into the corresponding
        Python value.
        """
        if column_type.startswith('list_'):
            return self.column_to_list(column_type, value)
        else:
            return value

    def list_to_column(self, column_type, value):
        """
        Convert a python list value into a suitable value to put in a
        database column.
        """
        converter = self._list_item_to_string.get(column_type)
        if converter is None:
            list_value = value
        else:
            list_value = [converter(i) for i in value]
        return repr(list_value)

    def column_to_list(self, column_type, value):
        """
        Convert a value of a database column into the corresponding
        Python list value.
        """
        if value is None:
            return None
        list_value = ast.literal_eval(value)
        converter = self._string_to_list_item.get(column_type)
        if converter is None:
            return list_value
        return [converter(i) for i in list_value]


class Undefined:
    pass


class FieldRow:
    '''
    A FieldRow is an object that makes it possible to access to attributes of
    a database row returned by sqlalchemy using the column name. If the
    attribute with the field name is not found, it is hashed and search in the
    actual row. If found, it is stored in the FieldRow instance.
    '''

    def __init__(self, database, collection, row):
        self.database = database
        self.collection = collection
        self.row = row

    def __getattr__(self, name):
        try:
            return getattr(self.row, name)
        except AttributeError as e:
            hashed_name = hashlib.md5(name.encode('utf-8')).hexdigest()
            result = getattr(self.row, hashed_name, Undefined)
            if result is Undefined:
                raise
            result = self.database.column_to_python(
                self.database.get_field(self.collection, name).type, result)
            setattr(self, hashed_name, result)
            return result

    def __getitem__(self, name):
        return getattr(self, name)
