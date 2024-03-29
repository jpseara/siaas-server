# Intelligent System for Automation of Security Audits (SIAAS)
# Server - DB Maintenance module
# By João Pedro Seara, 2022-2024

import siaas_aux
import logging
import os
import sys
import time

logger = logging.getLogger(__name__)


def delete_history_data(db_collection, days_to_keep):
    """
    Receives a MongoDB collection and number of days to keep
    Deletes all documents older than those days
    Returns True if all OK; False if something failed
    """
    logger.info("Performing history database cleanup, keeping last " +
                str(days_to_keep)+" days ...")
    deleted_count = siaas_aux.delete_all_records_older_than(
        db_collection, scope="agent_data", agent_uid=None, days_to_keep=days_to_keep)
    if type(deleted_count) == bool and deleted_count == False:
        logger.error(
            "DB could not be cleaned up. This might result in an eventual disk exhaustion in the server!")
        return False
    else:
        logger.info("DB cleanup finished. " +
                    str(deleted_count)+" records deleted.")
        return True


def loop():
    """
    DB Maintenance loop (calls the delete historical data function)
    """
    # Generate global variables from the configuration file
    config_dict = siaas_aux.get_config_from_configs_db(convert_to_string=True)
    MONGO_USER = None
    MONGO_PWD = None
    MONGO_HOST = None
    MONGO_PORT = None
    MONGO_DB = None
    MONGO_COLLECTION = None
    for config_name in config_dict.keys():
        if config_name.upper() == "MONGO_USER":
            MONGO_USER = config_dict[config_name]
        if config_name.upper() == "MONGO_PWD":
            MONGO_PWD = config_dict[config_name]
        if config_name.upper() == "MONGO_HOST":
            MONGO_HOST = config_dict[config_name]
        if config_name.upper() == "MONGO_PORT":
            MONGO_PORT = config_dict[config_name]
        if config_name.upper() == "MONGO_DB":
            MONGO_DB = config_dict[config_name]
        if config_name.upper() == "MONGO_COLLECTION":
            MONGO_COLLECTION = config_dict[config_name]

    if len(MONGO_PORT or '') > 0:
        mongo_host_port = MONGO_HOST+":"+MONGO_PORT
    else:
        mongo_host_port = MONGO_HOST
    db_collection = siaas_aux.connect_mongodb_collection(
        MONGO_USER, MONGO_PWD, mongo_host_port, MONGO_DB, MONGO_COLLECTION)

    run = True
    if db_collection == None:
        logger.error(
            "No valid DB collection received. No DB maintenance will be performed.")
        run = False

    while run:

        logger.debug("Loop running ...")

        try:
            days_to_keep = int(siaas_aux.get_config_from_configs_db(
                config_name="dbmaintenance_history_days_to_keep"))
            if days_to_keep < 0:
                raise ValueError(
                    "Number of historical days can't be negative.")
        except:
            logger.debug(
                "The number of days to keep in the database is not configured or is invalid. Using the value of 2 weeks by default.")
            days_to_keep = 14

        delete_history_data(db_collection, days_to_keep)

        # Sleep before next loop
        try:
            sleep_time = int(siaas_aux.get_config_from_configs_db(
                config_name="dbmaintenance_loop_interval_sec"))
            logger.debug("Sleeping for "+str(sleep_time) +
                         " seconds before next loop ...")
            time.sleep(sleep_time)
        except:
            logger.debug(
                "The interval loop time is not configured or is invalid. Sleeping now for 1 day by default ...")
            time.sleep(86400)


if __name__ == "__main__":

    log_level = logging.INFO
    logging.basicConfig(
        format='%(asctime)s %(levelname)-5s %(filename)s [%(threadName)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=log_level)

    if os.geteuid() != 0:
        print("You need to be root to run this script!", file=sys.stderr)
        sys.exit(1)

    print('\nThis script is being directly run, so it will just read data from the DB!\n')

    siaas_uid = siaas_aux.get_or_create_unique_system_id()
    # siaas_uid = "00000000-0000-0000-0000-000000000000" # hack to show data from all agents

    MONGO_USER = "siaas"
    MONGO_PWD = "siaas"
    MONGO_HOST = "127.0.0.1"
    MONGO_PORT = "27017"
    MONGO_DB = "siaas"
    MONGO_COLLECTION = "siaas"

    try:
        collection = siaas_aux.connect_mongodb_collection(
            MONGO_USER, MONGO_PWD, MONGO_HOST+":"+MONGO_PORT, MONGO_DB, MONGO_COLLECTION)
    except:
        print("Can't connect to DB!")
        sys.exit(1)

    logger.info("Cleaning up the DB ...")

    delete_history_data(collection, days_to_keep=365)

    print('\nAll done. Bye!\n')
