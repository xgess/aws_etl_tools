import os
from datetime import datetime
import subprocess
import csv

from aws_etl_tools.s3_file import S3File, LOCAL_TEMP_DIRECTORY
from aws_etl_tools import config


def s3_to_redshift(s3_file, destination):
    file_path = s3_file.s3_path
    ingestion_class = destination.database.ingestion_class
    ingestor = ingestion_class(file_path, destination)
    ingestor()


def from_s3_file(s3_file, destination):
    s3_to_redshift(s3_file, destination)


def from_s3_path(s3_path, destination):
    s3_file = S3File(s3_path)
    from_s3_file(s3_file, destination)


def from_local_file(file_path, destination):
    s3_path = _transient_s3_path(destination)
    s3_file = S3File.from_local_file(file_path, s3_path)

    from_s3_file(s3_file, destination)


def from_in_memory(data, destination):
    file_path = _transient_local_path(destination)
    with open(file_path, 'w') as f:
        writer = csv.writer(f, delimiter=',')
        for row in data:
            writer.writerow(row)

    from_local_file(file_path, destination)


def from_dataframe(dataframe, destination, **df_kwargs):
    file_path = _transient_local_path(destination)
    arguments = {
        'index': False,
        'header': False
    }
    arguments.update(df_kwargs)
    dataframe.to_csv(file_path, **arguments)

    from_local_file(file_path, destination)


def from_postgres_query(database, query, destination):
    file_path = _transient_local_path(destination)
    with open(file_path, 'w') as f:
        subprocess.call([
                'psql',
                '-q',
                '-h', database.credentials['host'],
                '-U', database.credentials['username'],
                '-d', database.credentials['database_name'],
                '-p', str(database.credentials['port']),
                '-c', 'COPY ({}) TO STDOUT CSV'.format(query)
            ],
            env=dict(os.environ, PGPASSWORD=database.credentials['password']),
            stdout=f
        )

    from_local_file(file_path, destination)


def _destination_file_name(destination):
    return destination.unique_identifier + '.csv'


def _transient_local_path(destination):
    file_name = _destination_file_name(destination)
    return os.path.join(LOCAL_TEMP_DIRECTORY, file_name)


def _transient_s3_path(destination):
    base_s3_path = config.S3_BASE_PATH
    s3_subpath = _s3_ingest_subpath(destination)
    return os.path.join(base_s3_path, s3_subpath)


def _s3_ingest_subpath(destination):
    database_name = destination.database.__class__.__name__.lower()
    return os.path.join(
            database_name,
            destination.table_schema,
            _destination_file_name(destination)
        )