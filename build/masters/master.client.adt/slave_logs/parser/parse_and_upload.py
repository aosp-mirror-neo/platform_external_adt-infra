# This is a standalone script to parse emulator boot test log files
# It does,
# 1. read log files, extract boot time information
# 2. dump avd configuration and boot time to csv file
# 3. upload csv data file and error file to big query table
# 4. upload log files to google storage bucket for long-term archive
# 5. remove log files from local disk
#
# This file should be placed under [LogDIR]\parser\,
# BigQuery schema should be placed under the same directory and named "boot_time_csv_schema.json"
# The script also assume client secret file "LLDB_BUILD_SECRETS.json" exists under the same directory

import os
import re
import argparse
import json
import time
import zipfile
import subprocess
import logging
import traceback
from logging.handlers import RotatingFileHandler
from oauth2client.client import GoogleCredentials

from apiclient.http import MediaFileUpload

from googleapiclient import discovery
from time import gmtime, strftime
from shutil import copyfile

project_id = 'android-devtools-lldb-build'
dataset_id = 'emu_buildbot'

table_data = 'avd_to_time_data'
table_err = 'avd_to_time_error'

parser_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.join(parser_dir, "..")

file_data = os.path.join(parser_dir, "AVD_to_time_data.csv")
file_err = os.path.join(parser_dir, "AVD_to_time_error.csv")
schema_path = os.path.join(parser_dir, "boot_time_csv_schema.json")

result_re = re.compile(".*AVD (.*), boot time: (\d*.?\d*), expected time: \d+")
log_dir_re = re.compile("build_(\d+)-rev_(.*).zip")
avd_re = re.compile("([^-]*)-(.*)-(.*)-(\d+)-gpu_(.*)-api(\d+)")
start_re = re.compile(".*INFO - Running - (.*)")
timeout_re = re.compile(".*ERROR - AVD (.*) didn't boot up within (\d+) seconds")
fail_re = re.compile("^FAIL: test_boot_(.*)_qemu(\d+) \(test_boot.test_boot.BootTestCase\)$")

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = RotatingFileHandler(os.path.join(parser_dir, "parser_logs.txt"), maxBytes=1048576, backupCount=10)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

logger = logging.getLogger()
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)

hasData = False
hasError = False

# process a zip folder
def process_zipfile(zip_name, builder, csv_data, csv_err):
    global hasData, hasError
    zip_path = os.path.join(root_dir, builder, zip_name)
    logger.info("Process zip file %s", zip_name)
    if log_dir_re.match(zip_name):
        build, revision = log_dir_re.match(zip_name).groups()
    else:
        logger.info("Skip invalid directory %s", zip_name)
        return
    with zipfile.ZipFile(zip_path, 'r') as log_dir:
        for x in [log_file for log_file in log_dir.namelist() if not log_file.endswith('/')]:
            if any(s in x for s in ["CTS_test", "verbose", "logcat"]):
                continue
            #logger.info("parsing file %s ...", x)
            with log_dir.open(x) as f:
                for line in f:
                    is_timeout = False
                    is_fail = False
                    if start_re.match(line):
                        if "_qemu2" in line:
                            is_qemu2 = True
                        else:
                            is_qemu2 = False
                    if timeout_re.match(line):
                        is_timeout = True
                    elif fail_re.match(line):
                        is_fail = True
                    gr = result_re.match(line)
                    if gr is not None or is_timeout or is_fail:
                        if is_timeout:
                            boot_time = 9999
                            avd = timeout_re.match(line).groups()[0]
                        elif is_fail:
                            boot_time = 0.0
                            avd = fail_re.match(line).groups()[0]
                            is_qemu2 = (fail_re.match(line).groups()[1] == "2")
                        else:
                            avd, boot_time = gr.groups()
                        tag, abi, device, ram, gpu, api = avd_re.match(avd).groups()
                        record_line = "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (api, tag, abi, device, ram, gpu, "qemu2" if is_qemu2 else "qemu1", builder, build, revision, boot_time)
                        if is_timeout or is_fail:
                            csv_err.write(record_line)
                            hasError = True
                        else:
                            csv_data.write(record_line)
                            hasData = True
    dst_path = "gs://emu_test_traces/%s/" % builder
    logger.info("upload file to Google Storage - %s to %s ", zip_path, dst_path)
    subprocess.check_call(["/home/user/bin/gsutil", "mv", zip_path, dst_path])

def parse_logs():
    """Parse zipped log files and write to file in csv format"""

    with open(file_data, 'w') as csv_data, open(file_err, 'w') as csv_err:
        for x in os.listdir(root_dir):
            builder = x
            logger.info("Builder: %s", builder)
            builder_dir = os.path.join(root_dir, builder)
            if os.path.isdir(builder_dir):
                for zip_dir in [x for x in os.listdir(builder_dir) if x.endswith(".zip")]:
                    process_zipfile(zip_dir, builder, csv_data, csv_err)

def load_data(data_path, table_id):
    """Loads the given data file into BigQuery.

    Args:
        schema_path: the path to a file containing a valid bigquery schema.
            see https://cloud.google.com/bigquery/docs/reference/v2/tables
        data_path: the name of the file to insert into the table.
        project_id: The project id that the table exists under. This is also
            assumed to be the project id this request is to be made under.
        dataset_id: The dataset id of the destination table.
        table_id: The table id to load data into.
    """
    # Create a bigquery service object, using the application's default auth
    logger.info('Upload %s to table %s', data_path, table_id)
    credentials = GoogleCredentials.get_application_default()
    bigquery = discovery.build('bigquery', 'v2', credentials=credentials)

    # Infer the data format from the name of the data file.
    source_format = 'CSV'
    if data_path[-5:].lower() == '.json':
        source_format = 'NEWLINE_DELIMITED_JSON'

    # Post to the jobs resource using the client's media upload interface. See:
    # http://developers.google.com/api-client-library/python/guide/media_upload
    insert_request = bigquery.jobs().insert(
        projectId=project_id,
        # Provide a configuration object. See:
        # https://cloud.google.com/bigquery/docs/reference/v2/jobs#resource
        body={
            'configuration': {
                'load': {
                    'schema': {
                        'fields': json.load(open(schema_path, 'r'))
                    },
                    'destinationTable': {
                        'projectId': project_id,
                        'datasetId': dataset_id,
                        'tableId': table_id
                    },
                    'sourceFormat': source_format,
                }
            }
        },
        media_body=MediaFileUpload(
            data_path,
            mimetype='application/octet-stream'))
    job = insert_request.execute()

    logger.info('Waiting for job to finish...')

    status_request = bigquery.jobs().get(
        projectId=job['jobReference']['projectId'],
        jobId=job['jobReference']['jobId'])

    # Poll the job until it finishes.
    while True:
        result = status_request.execute(num_retries=2)

        if result['status']['state'] == 'DONE':
            if result['status'].get('errors'):
                raise RuntimeError('\n'.join(
                    e['message'] for e in result['status']['errors']))
            logger.info('Job complete.')
            return

        time.sleep(1)

if __name__ == "__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(parser_dir, "LLDB_BUILD_SECRETS.json")

    def back_up():
        for x in [file_data, file_err]:
            dst = "%s_%s" % (x, strftime("%Y%m%d-%H%M%S"))
            copyfile(x, dst)
    try:
        logging.info("Start log parser ...")
        parse_logs()
    except:
        logging.info(traceback.format_exc())
        back_up()
        exit(0)
    try:
        if hasData:
            load_data(file_data, table_data)
        else:
            logging.info("No test data found, skip uploading data table.")
        if hasError:
            load_data(file_err, table_err)
        else:
            logging.info("No test error found, skip uploading error table.")
    except:
        logging.info(traceback.format_exc())
        back_up()
