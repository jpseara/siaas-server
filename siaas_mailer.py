# Intelligent System for Automation of Security Audits (SIAAS)
# Server - Mailer module
# By João Pedro Seara, 2022-2024

import siaas_aux
import smtplib
import ssl
import csv
import platform
import json
import os
import sys
import logging
import time
from pathlib import Path
from datetime import datetime
from email.utils import formataddr
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)


def send_siaas_email(db_collection, smtp_account, smtp_pwd, smtp_receivers, smtp_server, smtp_tls_port, smtp_report_type, last_dict=None):
    """
    Receives the DB collection and SMTP server details, and the last data dict that was sent
    If changes are detected in the data dict, an email is sent. Otherwise, nothing happens
    Returns the new data dict if all OK; Returns the last dict if no changes were detected or if something has failed
    """
    logger.info("Generating a new email report to send ...")

    out_dict = siaas_aux.get_dict_current_agent_data(
        db_collection, agent_uid=None, module="portscanner")

    if out_dict == False:
        logger.error(
            "There was an error getting agent data to be sent in the email. Not sending any email.")
        return last_dict

    new_dict = siaas_aux.grab_vulns_from_agent_data_dict(
        out_dict, report_type=smtp_report_type)

    if new_dict == False:
        logger.error(
            "There was an error parsing vulnerability data to be sent in the email. Not sending any email.")
        return last_dict

    if str(new_dict) == str(last_dict) and last_dict != None:
        logger.info("No new data to report. Not sending any email.")
        return last_dict

    if smtp_report_type.lower() == "all":
        mail_type = "All scanned data"
        csv_type = "all"
    elif smtp_report_type.lower() == "exploit_vuln_only":
        mail_type = "Exploits"
        csv_type = "exploits"
    else:
        mail_type = "Vulnerabilities"
        csv_type = "vulns"

    last_dict = new_dict
    signature = "Server UID: " + siaas_aux.get_or_create_unique_system_id() + \
        "\nServer IP: " + siaas_aux.get_main_ip_address()

    if len(new_dict) == 0:
        mail_body = "Nothing to report."
    else:
        #mail_body = pprint.pformat(new_dict, width=999, sort_dicts=False)
        mail_body = "Report attached."
    mail_body = mail_body + "\n\n" + signature

    # Create a CSV report

    csv_contents = []
    for a in new_dict.keys():
        for b in new_dict[a].keys():
            for c in new_dict[a][b].keys():
                for d in new_dict[a][b][c].keys():
                    csv_contents.append([a, c, d, json.dumps(
                        new_dict[a][b][c][d], sort_keys=False, ensure_ascii=False)])

    csv_delimiter = ';'
    file_to_write = "./tmp/siaas_report_" + csv_type + "_" + siaas_aux.get_or_create_unique_system_id() + \
        "_" + datetime.utcnow().strftime('%Y%m%d%H%M%S')+".csv"
    os.makedirs(os.path.dirname(os.path.join(
        sys.path[0], file_to_write)), exist_ok=True)
    with open(file_to_write, 'w') as f:
        w = csv.writer(f, delimiter=csv_delimiter)
        w.writerow(["AgentUID", "TargetHost", "InformationType", "Findings"])
        w.writerows(csv_contents)

    # Message headers
    message = MIMEMultipart("alternative")
    message["Subject"] = "SIAAS Report ("+mail_type+") from "+platform.node().split('.', 1)[
        0]+" on "+datetime.now().strftime('%Y-%m-%d at %H:%M')+" "+datetime.now().astimezone().tzname()
    #message["From"] = smtp_account
    message["From"] = formataddr(
        ("SIAAS Server ("+platform.node().split('.', 1)[0]+")", smtp_account))
    message["To"] = smtp_receivers

    # Create the MIMEText object
    part1 = MIMEText(mail_body, "plain")
    message.attach(part1)

    with open(file_to_write, "r") as file:
        part = MIMEApplication(
            file.read(),
            Name=os.path.basename(file_to_write)
        )
    part['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(
        file_to_write)

    if len(new_dict) > 0:
        message.attach(part)

    # Create secure connection with server and send email
    try:
        context = ssl.create_default_context()
        smtp_receivers_list = sorted(set(smtp_receivers.split(
            ',')), key=lambda x: x.casefold() if len(x or "") > 0 else "")
        with smtplib.SMTP(smtp_server, smtp_tls_port) as server:
            server.starttls(context=context)
            server.login(smtp_account, smtp_pwd)
            server.sendmail(
                smtp_account, smtp_receivers_list, message.as_string()
            )

        Path(file_to_write).unlink(missing_ok=True)
    except Exception as e:
        logger.error("Error while sending email report: "+str(e))
        return last_dict

    logger.info("Report sent via email.")
    logger.debug("Sent email contents:\n"+str(mail_body))
    return new_dict


def loop():
    """
    Mailer module loop (calls the email sending function)
    """
    # Generate global variables from the configurations DB
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

    last_dict = None
    while run:

        send_mail = True

        logger.debug("Loop running ...")

        mailer_smtp_account = siaas_aux.get_config_from_configs_db(
            config_name="mailer_smtp_account")
        mailer_smtp_pwd = siaas_aux.get_config_from_configs_db(
            config_name="mailer_smtp_pwd")
        mailer_smtp_recipients = siaas_aux.get_config_from_configs_db(
            config_name="mailer_smtp_recipients")
        mailer_smtp_server = siaas_aux.get_config_from_configs_db(
            config_name="mailer_smtp_server")
        mailer_smtp_tls_port = siaas_aux.get_config_from_configs_db(
            config_name="mailer_smtp_tls_port")
        mailer_smtp_report_type = siaas_aux.get_config_from_configs_db(
            config_name="mailer_smtp_report_type")

        if len(mailer_smtp_recipients or '') == 0:
            logger.info(
                "No email receivers are defined. Not sending any emails.")
            send_mail = False

        elif len(mailer_smtp_account or '') == 0 or len(mailer_smtp_pwd or '') == 0 or len(mailer_smtp_server or '') == 0:
            logger.warning(
                "One or more of the mailer configuration fields are undefined or invalid. Not sending any emails.")
            send_mail = False

        if send_mail:

            if len(mailer_smtp_report_type or '') == 0:
                logger.debug(
                    "No report type configured. Defaulting to 'vuln_only'.")
                mailer_smtp_report_type = "vuln_only"

            try:
                smtp_tls_port = int(mailer_smtp_tls_port)
                if smtp_tls_port < 1:
                    raise ValueError("SMTP TLS port can't be less 1.")
            except:
                smtp_tls_port = 25
                logger.debug(
                    "SMTP TLS port is invalid or not defined. Using SMTP TLS port default (587).")

            if send_mail:
                last_dict = send_siaas_email(db_collection, mailer_smtp_account, mailer_smtp_pwd,
                                             mailer_smtp_recipients, mailer_smtp_server, smtp_tls_port, mailer_smtp_report_type, last_dict)

        # Sleep before next loop
        try:
            sleep_time = int(siaas_aux.get_config_from_configs_db(
                config_name="mailer_loop_interval_sec"))
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

    logger.info("Sending an email ...")

    smtp_account = "siaas.iscte@gmail.com"
    smtp_receivers = "siaas.iscte@gmail.com"
    smtp_pwd = "password123"
    smtp_server = "smtp.gmail.com"
    smtp_tls_port = "587"
    # all, vuln_only (default), exploit_vuln_only
    smtp_report_type = "exploit_vuln_only"

    send_siaas_email(collection, smtp_account, smtp_pwd,
                     smtp_receivers, smtp_server, smtp_tls_port, smtp_report_type)

    print('\nAll done. Bye!\n')
