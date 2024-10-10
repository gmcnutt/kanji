#!/bin/bash

DBNAME=kanji.db
SCHEMAFILE=schema.sql
#INITFILE=init.sqlite3

# Create the database and schema
sqlite3 $DBNAME < $SCHEMAFILE

# Initialize tables from the archive
#sqlite3 $DBNAME < $INITFILE
