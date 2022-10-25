import ipaddress
import scapy.config
import scapy.layers.l2
import scapy.route
import math
import dns.resolver
import pprint
import logging
import uuid
import os
import sys
import json
from copy import copy
from datetime import datetime, timedelta
from pymongo import MongoClient
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


def merge_module_dicts(modules=""):
    """
    Grabs all DB files from the module list and concatenate them
    Returns an empty dict if it fails
    """
    merged_dict = {}
    for module in modules.split(','):
        module = module.lstrip().rstrip()
        try:
            module_dict = read_from_local_file(
                os.path.join(sys.path[0], 'var/'+str(module)+'.db'))
            if module_dict != None:
                next_dict_to_merge = {}
                next_dict_to_merge[module] = module_dict
                merged_dict = dict(
                  list(merged_dict.items())+list(next_dict_to_merge.items()))
        except:
            logger.warning("Couldn't merge dict: " +
                           str(next_dict_to_merge))
    return merged_dict


def merge_configs_from_upstream(local_dict=os.path.join(sys.path[0], 'var/config_orig.db'), output=os.path.join(sys.path[0], 'var/config.db'), upstream_dict={}):
    """
    Merges the configs downloaded from the server to the local configs DB;
    If the config disappears from the server, it reverts to the local config.
    """
    merged_config_dict = {}
    delta_dict = {}
    try:
        local_config_dict = get_config_from_configs_db(local_dict=local_dict)
        if len(upstream_dict) > 0:
            logger.debug("The following configurations are being applied/overwritten from the server: "+str(upstream_dict))
        else:
            logger.debug("No configurations were found in the remote server. Using local configurations only.")
        merged_config_dict = dict(list(local_config_dict.items())+list(upstream_dict.items()))
    except:
        logger.error(
            "Could not merge configurations from remote server with the local configs.")
    return write_to_local_file(output, merged_config_dict)


def get_config_from_configs_db(local_dict=os.path.join(sys.path[0], 'var/config.db'), config_name=None, convert_to_string=True):
    """
    Reads a configuration value from the configs db
    If the intput is "None" it returns an entire dict with all the values. Returns an empty dict if there are no configs
    If the input is a specific config key, it returns the value for that config key. Returns None if the config key does not exist
    """
    if config_name == None:

        logger.debug("Getting configuration dictionary from local DB ...")
        config_dict = read_from_local_file(
            local_dict)
        if len(config_dict or '') > 0:
            out_dict = {}
            for k in config_dict.keys():
                if convert_to_string:
                   out_dict[k]=str(config_dict[k])
                else:
                   out_dict[k]=config_dict[k]
            return config_dict

        logger.error("Couldn't get configuration dictionary from local DB.")
        return {}

    else:

        logger.debug("Getting configuration value '" +
                     config_name+"' from local DB ...")
        config_dict = read_from_local_file(
            local_dict)
        if len(config_dict or '') > 0:
            if config_name in config_dict.keys():
                value=config_dict[config_name]
                if convert_to_string:
                    value=str(value)
                return config_dict[config_name]

        logger.debug("Couldn't get configuration named '" +
                     config_name+"' from local DB. Maybe it doesn't exist.")
        return None


def write_config_db_from_conf_file(conf_file=os.path.join(sys.path[0], 'conf/siaas_server.cnf'), output=os.path.join(sys.path[0], 'var/config.db')):
    """
    Writes the configuration DB (dict) from the config file. If the file is empty or does not exist, returns False
    It will strip all characters after '#', and then strip the spaces from the beginning or end of the resulting string. If the resulting string is empty, it will ignore it
    Then, it will grab the string before the first "=" as the config key, and after it as the actual value
    The config key has its spaces removed from beginning or end, and all " and ' are removed.
    The actual value is just stripped of spaces from the beginning and the end
    Writes the resulting dict in the DB file of config.db. This means it will return True if things go fine, or False if it fails
    """

    logger.debug("Writing configuration local DB, from local file: "+conf_file)

    config_dict = {}

    local_conf_file = read_from_local_file(conf_file)
    if len(local_conf_file or '') == 0:
        return False

    for line in local_conf_file.splitlines():
        try:
            line_uncommented = line.split('#')[0].rstrip().lstrip()
            if len(line_uncommented) == 0:
                continue
            config_name = line_uncommented.split("=", 1)[0].rstrip().lstrip().replace("\"", "").replace("\'", "")
            config_value = line_uncommented.split("=", 1)[1].rstrip().lstrip()
            config_dict[config_name] = config_value
        except:
            logger.warning("Invalid line from local config file: "+str(line))
            continue

    return write_to_local_file(output, config_dict)


def read_mongodb_collection(collection, siaas_uid="00000000-0000-0000-0000-000000000000"):
    """
    Reads data from the Mongo DB collection
    If the UID is "nil" it will return all records. Else, it will return records only for the inputted UID
    Returns a list of records. Returns None if data can't be read
    """
    logger.debug("Reading data from the remote DB server ...")
    try:

        if(siaas_uid == "00000000-0000-0000-0000-000000000000"):
            cursor = collection.find({"payload": {'$exists': True}}).sort('_id', -1).limit(15) # show everything
        else:
            cursor = collection.find({'$and': [{"payload": {'$exists': True}}, {'$or':[{"origin": "server_"+siaas_uid}, {"destiny": {'$in': ["server_"+siaas_uid, "server_ffffffff-ffff-ffff-ffff-ffffffffffff"]}}]}]}).sort('_id', -1).limit(15)  # destinated or originated to/from the server

        results = list(cursor)
        for doc in results:
            logger.debug("Record read: "+str(doc))
        return results
    except Exception as e:
        logger.error("Can't read data from remote DB server: "+str(e))
        return None

def get_dict_active_agents(collection):
    """
    Reads a list of active agents
    Returns a list of records. Returns empty dict if data can't be read
    """
    logger.debug("Reading data from the remote DB server ...")
    out_dict={}

    try:
        if "timestamp" not in str(list(collection.index_information())):
             collection.create_index("timestamp", unique=False)
        cursor = collection.aggregate([
             { "$match": {"origin": { "$regex": "^agent_" }}},
             { "$sort": { "timestamp": 1 } },
             { "$group": { "_id": {"origin": "$origin"}, "origin": {"$last":"$origin"}, "timestamp": { "$last": "$timestamp" } } }
                 ] )
        results=list(cursor)
    except Exception as e:
        logger.error("Can't read data from remote DB server: "+str(e))
        return out_dict

    for r in results:
        try:
            uid=r["origin"].split("_",1)[1]
            out_dict[uid]={}
            out_dict[uid]["last_seen"]=r["timestamp"].strftime('%Y-%m-%dT%H:%M:%SZ')
        except:
            logger.debug("Ignoring invalid entry when grabbing active agents data.")

    return out_dict

def get_dict_historical_agent_data(collection, agent_uid=None, module=None, limit_outputs=99999, days=99999):
    """
    Reads historical agent data from the Mongo DB collection
    We can select a list of agents and modules to display
    Returns a list of records. Returns empty dict if data can't be read
    """
    logger.debug("Reading data from the remote DB server ...")
    out_dict={}


    if agent_uid == None:
        try:
            last_d = datetime.utcnow() - timedelta(days=int(days))
            cursor = collection.find(
                    {'$and': [{"payload": {'$exists': True}}, {"scope": "agent_data"}, {"timestamp":{"$gte": last_d}}
                       ]}
                     ).sort('_id', -1).limit(int(limit_outputs))
            results=list(cursor)
        except Exception as e:
            logger.error("Can't read data from remote DB server: "+str(e))
            return out_dict

    else:
        results=[]
        agent_list=[]
        for u in agent_uid.split(','):
            agent_list.append("agent_"+u.lstrip().rstrip())
        try:
            last_d = datetime.utcnow() - timedelta(days=int(days))
            cursor = collection.find(
               {'$and': [{"payload": {'$exists': True}}, {"scope": "agent_data"}, {"timestamp":{"$gte": last_d}}, {"origin": {'$in': agent_list}}]}
                 ).sort('_id', -1).limit(int(limit_outputs))
            results=results+list(cursor)
        except Exception as e:
            logger.error("Can't read data from remote DB server: "+str(e))

    for r in results:
        try:
            if r["origin"].startswith("agent_"):
                uid=r["origin"].split("_",1)[1]
                timestamp=r["timestamp"].strftime('%Y-%m-%dT%H:%M:%SZ')
                if timestamp not in out_dict.keys():
                   out_dict[timestamp]={}
                if module == None:
                   out_dict[timestamp][uid]=r["payload"]
                else:
                   out_dict[timestamp][uid]={}
                   for m in module.split(','):
                       mod=m.lstrip().rstrip()
                       if mod in r["payload"].keys():
                           out_dict[timestamp][uid][mod]=r["payload"][mod]
        except:
            logger.debug("Ignoring invalid entry when grabbing agent data.")

    return out_dict


def get_dict_current_agent_data(collection, agent_uid=None, module=None):
    """
    Reads agent data from the Mongo DB collection
    We can select a list of agents and modules to display
    Returns a list of records. Returns empty dict if data can't be read
    """
    logger.debug("Reading data from the remote DB server ...")
    out_dict={}

    if agent_uid == None:
        try:
            if "timestamp" not in str(list(collection.index_information())):
                collection.create_index("timestamp", unique=False)
            cursor = collection.aggregate([
                { "$match": {'$and': [{"origin": { "$regex": "^agent_" }}, {"scope": "agent_data"}]}},
                { "$sort": { "timestamp": 1 } },
                { "$group": { "_id": {"origin": "$origin"}, "scope": {"$last":"$scope"}, "origin": {"$last":"$origin"}, "destiny": {"$last":"$destiny"}, "payload": {"$last":"$payload"}, "timestamp": { "$last": "$timestamp" } } }
                      ] )
            results=list(cursor)
        except Exception as e:
            logger.error("Can't read data from remote DB server: "+str(e))
            return out_dict

    else:
        results=[]
        for u in agent_uid.split(','):
            uid=u.lstrip().rstrip()
            try:
                cursor = collection.find(
                   {'$and': [{"payload": {'$exists': True}}, {"scope": "agent_data"}, {"origin": "agent_"+uid}]}
                     ).sort('_id', -1).limit(1)
                results=results+list(cursor)
            except Exception as e:
                logger.error("Can't read data from remote DB server: "+str(e))

    for r in results:
        try:
            if r["origin"].startswith("agent_"):
                uid=r["origin"].split("_",1)[1]
                if module == None:
                   out_dict[uid]=r["payload"]
                else:
                   out_dict[uid]={}
                   for m in module.split(','):
                       mod=m.lstrip().rstrip()
                       if mod in r["payload"].keys():
                           out_dict[uid][mod]=r["payload"][mod]
        except:
            logger.debug("Ignoring invalid entry when grabbing agent data.")

    return out_dict


def get_dict_current_agent_configs(collection, agent_uid=None, merge_broadcast=False):
    """
    Reads agent data from the Mongo DB collection
    We can select a list of agents and modules to display
    Returns a list of records. Returns empty dict if data can't be read
    """
    logger.debug("Reading data from the remote DB server ...")
    out_dict={}

    if agent_uid == None:
        try:
            if "timestamp" not in str(list(collection.index_information())):
                collection.create_index("timestamp", unique=False)
            cursor = collection.aggregate([
                { "$match": {'$and': [{"destiny": { "$regex": "^agent_" }}, {"scope": "agent_configs"}]}},
                { "$sort": { "timestamp": 1 } },
                { "$group": { "_id": {"destiny": "$destiny"}, "scope": {"$last":"$scope"}, "origin": {"$last":"$origin"}, "destiny": {"$last":"$destiny"}, "payload": {"$last":"$payload"}, "timestamp": { "$last": "$timestamp" } } }
                      ] )
            results=list(cursor)
        except Exception as e:
            logger.error("Can't read data from remote DB server: "+str(e))
            return out_dict

    else:
        results=[]
        for u in agent_uid.split(','):
            uid=u.lstrip().rstrip()
            try:
                cursor = collection.find(
                   {'$and': [{"payload": {'$exists': True}}, {"scope": "agent_configs"}, {"destiny": "agent_"+uid}]}
                     ).sort('_id', -1).limit(1)
                results=results+list(cursor)
            except Exception as e:
                logger.error("Can't read data from remote DB server: "+str(e))
            
    if merge_broadcast:
        results_bc=[]
        try:
            cursor = collection.find(
               {'$and': [{"payload": {'$exists': True}}, {"scope": "agent_configs"}, {"destiny": "agent_ffffffff-ffff-ffff-ffff-ffffffffffff"}]}
                 ).sort('_id', -1).limit(1)
            results_bc=list(cursor)
        except Exception as e:
            logger.error("Can't read data from remote DB server: "+str(e))

    for r in results:
        try:
            if r["destiny"].startswith("agent_"):
                    uid=r["destiny"].split("_",1)[1]
                    if merge_broadcast:
                        if len(results_bc)>0:
                            out_dict[uid]=dict(list(results_bc[0]["payload"].items())+list(r["payload"].items()))
                        else:
                            out_dict[uid]=r["payload"]
                    else:
                       out_dict[uid]=r["payload"]
        except:
            logger.debug("Ignoring invalid entry when grabbing agent data.")

    return out_dict

def read_published_data_for_agents_mongodb(collection, siaas_uid="00000000-0000-0000-0000-000000000000", scope=None, include_broadcast=False, convert_to_string=False):
    """
    Reads data from the Mongo DB collection, specifically published by the server, for agents
    Returns a config dict. Returns an empty dict if anything failed
    """
    my_configs = {}
    broadcasted_configs = {}
    out_dict = {}
    logger.debug("Reading data from the remote DB server ...")
    try:
        if len(scope or '') > 0:
            cursor1 = collection.find({"payload": {'$exists': True}, "destiny": "agent_"+siaas_uid, "scope": scope}, {'_id': False, 'timestamp': False, 'origin': False, 'destiny': False, 'scope': False}).sort('_id', -1).limit(1)
        else:
            cursor1 = collection.find({"payload": {'$exists': True}, "destiny": "agent_"+siaas_uid}, {'_id': False, 'timestamp': False, 'origin': False, 'destiny': False, 'scope': False}).sort('_id', -1).limit(1)
        results1 = list(cursor1)
        for doc in results1:
            my_configs = doc["payload"]

        if len(scope or '') > 0:
            cursor2 = collection.find({"payload": {'$exists': True}, "destiny": "agent_"+"ffffffff-ffff-ffff-ffff-ffffffffffff", "scope": scope}, {'_id': False, 'timestamp': False, 'origin': False, 'destiny': False, 'scope': False}).sort('_id', -1).limit(1)
        else:
            cursor2 = collection.find({"payload": {'$exists': True}, "destiny": "agent_"+"ffffffff-ffff-ffff-ffff-ffffffffffff"}, {'_id': False, 'timestamp': False, 'origin': False, 'destiny': False, 'scope': False}).sort('_id', -1).limit(1)
        results2 = list(cursor2)
        for doc in results2:
            broadcasted_configs = doc["payload"]

        if include_broadcast:
            final_results = dict(
                list(broadcasted_configs.items())+list(my_configs.items())) # configs directed to the agent have precedence over broadcasted ones
        else:
            final_results = my_configs

        for k in final_results.keys():
            if convert_to_string:
                out_dict[k]=str(final_results[k])
            else:
                out_dict[k]=final_results[k]

        logger.debug("Records read from the server: "+str(out_dict))
    except Exception as e:
        logger.error("Can't read data from remote DB server: "+str(e))
    return out_dict


def insert_in_mongodb_collection(collection, data_to_insert):
    """
    Inserts data (usually a dict) into a said collection
    Returns True if all was OK. Returns False if the insertion failed
    """
    logger.debug("Inserting data in the remote DB server ...")
    try:
        logger.debug("All data that will now be written to the database:\n" +
                     pprint.pformat(data_to_insert))
        collection.insert_one(copy(data_to_insert))
        logger.debug("Data successfully uploaded to the remote DB server.")
        return True
    except Exception as e:
        logger.error("Can't upload data to remote DB server: "+str(e))
        return False


def create_or_update_in_mongodb_collection(collection, data_to_insert):
    """
    Creates or updates an object with data
    Returns True if all was OK. Returns False if the insertion failed
    """
    logger.info("Inserting data in the remote DB server ...")
    try:
        logger.debug("All data that will now be written to the database:\n" +
                     pprint.pformat(data_to_insert))
        data = copy(data_to_insert)
        collection.find_one_and_update(
            {'destiny': data["destiny"], 'scope': data["scope"]}, {'$set': data}, upsert=True)
        logger.info("Data successfully uploaded to the remote DB server.")
        return True
    except Exception as e:
        logger.error("Can't upload data to remote DB server: "+str(e))
        return False


def connect_mongodb_collection(mongo_user="siaas", mongo_password="siaas", mongo_host="127.0.0.1:27017", mongo_db="siaas", mongo_collection="siaas"):
    """
    Set up a MongoDB collection connection based on the inputs
    Returns the collection obj if succeeded. Returns None if it failed
    """
    logger.debug("Connecting to remote DB server at "+str(mongo_host)+" ...")
    try:
        uri = "mongodb://%s:%s@%s/%s" % (quote_plus(mongo_user),
                                         quote_plus(mongo_password), mongo_host, mongo_db)
        client = MongoClient(uri)
        db = client[mongo_db]
        collection = db[mongo_collection]
        logger.info(
            "Correctly configured the remote DB server connection to collection '"+mongo_collection+"'.")
        return collection
    except Exception as e:
        logger.error("Can't connect to remote DB server: "+str(e))
        return None


def write_to_local_file(file_to_write, data_to_insert):
    """
    Writes data (usually a dict) to a local file, after converting it to a JSON format
    Returns True if all went OK
    Returns False if it failed
    """
    logger.debug("Inserting data to local file "+file_to_write+" ...")
    try:
        os.makedirs(os.path.dirname(os.path.join(
            sys.path[0], file_to_write)), exist_ok=True)
        logger.debug("All data that will now be written to the file:\n" +
                     pprint.pformat(data_to_insert))
        with open(file_to_write, 'w') as file:
            file.write(json.dumps(data_to_insert))
            logger.debug("Local file write ended successfully.")
            return True
    except Exception as e:
        logger.error(
            "There was an error while writing to the local file "+file_to_write+": "+str(e))
        return False


def read_from_local_file(file_to_read):
    """
    Reads data from local file and returns it
    It will return None if it failed
    """
    logger.debug("Reading from local file "+file_to_read+" ...")
    try:
        with open(file_to_read, 'r') as file:
            content = file.read()
            try:
                content = eval(content)
            except:
                pass
            return content
    except Exception as e:
        logger.error("There was an error reading from local file " +
                     file_to_read+": "+str(e))
        return None


def get_or_create_unique_system_id():
    """
    Reads the local UID file and returns it
    If this file does not exist or has no data, continues to generate an UID. If it has an invalid UID, it will return a nil UID
    Proceeds to try to generate an UID from local system data
    If this fails, generates a random one
    If all fails, returns a nil UID
    """
    logger.debug(
        "Searching for an existing UID and creating a new one if it doesn't exist ...")
    try:
        with open(os.path.join(sys.path[0], 'var/uid'), 'r') as file:
            content = file.read()
            if len(content or '') == 0:
                raise IOError(
                    "Nothing valid could be read from local UID file.")
            if content.split('\n')[0] == "ffffffff-ffff-ffff-ffff-ffffffffffff":
                logger.warning(
                    "Invalid ID, reserved for broadcast. Returning a nil UID.")
                return "00000000-0000-0000-0000-000000000000"
            logger.debug("Reusing existing UID: "+str(content))
            return content.split('\n')[0]
    except:
        pass
    logger.debug(
        "Existing UID not found. Creating a new one from system info ...")
    new_uid = ""
    try:
        with open("/sys/class/dmi/id/board_serial", 'r') as file:
            content = file.read()
            new_uid = content.split('\n')[0]
    except:
        pass
    if len(new_uid) == 0:
        try:
            with open("/sys/class/dmi/id/product_uuid", 'r') as file:
                content = file.read()
                new_uid = content.split('\n')[0]
        except:
            pass
    if len(new_uid) == 0:
        try:
            with open("/var/lib/dbus/machine-id", 'r') as file:
                content = file.read()
                new_uid = content.split('\n')[0]
        except:
            pass
    if len(new_uid) == 0:
        logger.warning(
            "Couldn't create a new UID from the system info. Creating a new one on-the-fly ...")
        try:
            new_uid = str(uuid.UUID(int=uuid.getnode()))
        except:
            logger.error(
                "There was an error while generating a new UID. Returning a nil UID.")
            return "00000000-0000-0000-0000-000000000000"
    try:
        os.makedirs(os.path.join(sys.path[0], 'var'), exist_ok=True)
        with open(os.path.join(sys.path[0], 'var/uid'), 'w') as file:
            file.write(new_uid)
            logger.debug("Wrote new UID to a local file: "+new_uid)
    except Exception as e:
        logger.error("There was an error while writing to the local UID file: " +
                     str(e)+". Returning a nil UID.")
        return "00000000-0000-0000-0000-000000000000"
    return new_uid


def get_size(bytes, suffix="B"):
    """
    Scale bytes to its proper format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f} {unit}{suffix}"
        bytes /= factor


def get_now_utc_str():
    """
    Returns an ISO date string
    """
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def get_now_utc_obj():
    """
    Returns an ISO date obj
    """
    return datetime.strptime(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), '%Y-%m-%dT%H:%M:%SZ')


def is_ipv4_or_ipv6(ip):
    """
    Returns "6" if input IP is IPv6
    Returns "4" if input IP is IPv4
    Else returns None
    """
    try:
        ipaddress.IPv4Network(ip)
        return "4"
    except:
        pass
    try:
        ipaddress.IPv6Network(ip)
        return "6"
    except:
        return None


def get_ipv6_cidr(mask):
    """
    Returns the IPv6 short netmask from a long netmask input
    Returns None if inputted mask is not proper
    """
    bitCount = [0, 0x8000, 0xc000, 0xe000, 0xf000, 0xf800, 0xfc00, 0xfe00,
                0xff00, 0xff80, 0xffc0, 0xffe0, 0xfff0, 0xfff8, 0xfffc, 0xfffe, 0xffff]
    count = 0
    try:
        for w in mask.split(':'):
            if not w or int(w, 16) == 0:
                break
            count += bitCount.index(int(w, 16))
    except:
        return None
        logger.warning("Bad IPv6 netmask: "+mask)
    return count


def get_all_ips_for_name(host):
    """
    Checks all registered DNS IPs for a said host and returns them in a set
    If the input is already an IP address, returns it
    Returns an empty set if no IPs are found 
    """
    ips = set()

    # Check if the host is already an IP and return it
    try:
        ipaddress.IPv4Network(host)
        ips.add(host)
        return ips
    except:
        pass
    try:
        ipaddress.IPv6Network(host)
        ips.add(host)
        return ips
    except:
        pass

    # IPv4 name resolution
    try:
        result = dns.resolver.resolve(host, "A")
        for ipval in result:
            ips.add(ipval.to_text())
    except:
        pass

    # IPv6 name resolution
    try:
        result6 = dns.resolver.resolve(host, "AAAA")
        for ipval in result6:
            ips.add(ipval.to_text())
    except:
        pass

    return ips


def long2net(arg):
    """
    Converts an hexadecimal IPv4 netmask to a 0-32 integer
    """
    if (arg <= 0 or arg >= 0xFFFFFFFF):
        raise ValueError("Illegal netmask value", hex(arg))
    return 32 - int(round(math.log(0xFFFFFFFF - arg, 2)))


def to_cidr_notation(bytes_network, bytes_netmask):
    """
    Converts a network and network mask inputs in bytes to a network/short_mask IPv4 CIDR notation
    """
    network = scapy.utils.ltoa(bytes_network)
    netmask = long2net(bytes_netmask)
    net = "%s/%s" % (network, netmask)

    return net