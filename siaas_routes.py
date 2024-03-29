# Intelligent System for Automation of Security Audits (SIAAS)
# Server - API routes
# By João Pedro Seara, 2022-2024

from __main__ import app, get_db_collection
from flask import jsonify, request
import siaas_aux

SIAAS_VERSION = "1.0.1"

app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False


@app.route('/', strict_slashes=False)
def index():
    """
    Server API route - index
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    output = {
        'name': 'Intelligent System for Automation of Security Audits (SIAAS)',
        'module': 'Server',
        'version': SIAAS_VERSION,
        'docs': request.url_root.rstrip('/')+"/api/docs"
    }
    return jsonify(
        {
            'output': output,
            'status': 'success',
            'total_entries': len(output),
            'time': siaas_aux.get_now_utc_str()
        }
    ), ret_code


@app.route('/siaas-server', methods=['GET'], strict_slashes=False)
def siaas_server():
    """
    Server API route - server information
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    module = request.args.get('module', default='*', type=str)
    all_existing_modules = "platform,config"
    siaas_aux.merge_configs_from_upstream(
        upstream_dict=siaas_aux.get_dict_current_server_configs(get_db_collection()))
    for m in module.split(','):
        if m.strip() == "*":
            module = all_existing_modules
    output = siaas_aux.merge_module_dicts(module)
    if type(output) == bool and output == False:
        status = "failure"
        ret_code = 500
        output = {}
    else:
        status = "success"
    try:
        for k in output["config"].keys():
            if k.endswith("_pwd") or k.endswith("_passwd") or k.endswith("_password"):
                output["config"][k] = '*' * 8
    except:
        pass
    return jsonify(
        {
            'output': output,
            'status': status,
            'total_entries': len(output),
            'time': siaas_aux.get_now_utc_str()
        }
    ), ret_code


@app.route('/siaas-server/configs', methods=['GET', 'POST', 'DELETE'], strict_slashes=False)
def server_configs():
    """
    Server API route - server published configs
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    collection = get_db_collection()
    if request.method == 'GET':
        output = siaas_aux.get_dict_current_server_configs(
            collection)
        if type(output) == bool and output == False:
            status = "failure"
            ret_code = 500
            output = {}
        else:
            status = "success"
        return jsonify(
            {
                'output': output,
                'status': status,
                'total_entries': len(output),
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code
    if request.method == 'POST':
        content = request.json
        output = siaas_aux.create_or_update_server_configs(
            collection, config_dict=content, orig_ip=ip)
        if output:
            siaas_aux.merge_configs_from_upstream(
                upstream_dict=siaas_aux.get_dict_current_server_configs(collection))
            status = "success"
        else:
            status = "failure"
            ret_code = 500
        return jsonify(
            {
                'status': status,
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code
    if request.method == 'DELETE':
        output = siaas_aux.delete_all_records_older_than(
            collection, scope="server_configs", days_to_keep=0)
        if type(output) == bool and output == False:
            status = "failure"
            ret_code = 500
            count_deleted = 0
        else:
            siaas_aux.merge_configs_from_upstream(
                upstream_dict=siaas_aux.get_dict_current_server_configs(collection))
            status = "success"
            count_deleted = int(output)
        return jsonify(
            {
                'deleted_count': count_deleted,
                'status': status,
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code


@app.route('/siaas-server/agents', methods=['GET'], strict_slashes=False)
def agents():
    """
    Server API route - agents overview
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    collection = get_db_collection()
    sort_by = request.args.get('sort', default="date", type=str)
    output = siaas_aux.get_dict_active_agents(collection, sort_by=sort_by)
    if type(output) == bool and output == False:
        status = "failure"
        ret_code = 500
        output = {}
    else:
        status = "success"
    return jsonify(
        {
            'output': output,
            'status': status,
            'total_entries': len(output),
            'time': siaas_aux.get_now_utc_str()
        }
    ), ret_code


@app.route('/siaas-server/agents/data', methods=['GET'], strict_slashes=False)
def agents_data():
    """
    Server API route - agents data
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    module = request.args.get('module', default='*', type=str)
    for m in module.split(','):
        if m.strip() == "*":
            module = None
    collection = get_db_collection()
    output = siaas_aux.get_dict_current_agent_data(collection, module=module)
    if type(output) == bool and output == False:
        status = "failure"
        ret_code = 500
        output = {}
    else:
        status = "success"
    return jsonify(
        {
            'output': output,
            'status': status,
            'total_entries': len(output),
            'time': siaas_aux.get_now_utc_str()
        }
    ), ret_code


@app.route('/siaas-server/agents/data/<agent_uid>', methods=['GET', 'POST', 'DELETE'], strict_slashes=False)
def agents_data_id(agent_uid):
    """
    Server API route - agents data (specific UIDs, comma-separated)
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    collection = get_db_collection()
    if request.method == 'GET':
        module = request.args.get('module', default='*', type=str)
        for m in module.split(','):
            if m.strip() == "*":
                module = None
        output = siaas_aux.get_dict_current_agent_data(
            collection, agent_uid=agent_uid, module=module)
        if type(output) == bool and output == False:
            status = "failure"
            ret_code = 500
            output = {}
        else:
            status = "success"
        return jsonify(
            {
                'output': output,
                'status': status,
                'total_entries': len(output),
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code
    if request.method == 'POST':
        content = request.json
        output = siaas_aux.upload_agent_data(
            collection, agent_uid=agent_uid, data_dict=content, orig_ip=ip)
        if output:
            status = "success"
        else:
            status = "failure"
            ret_code = 500
        return jsonify(
            {
                'status': status,
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code
    if request.method == 'DELETE':
        days = request.args.get('days', default=365, type=int)
        output = siaas_aux.delete_all_records_older_than(
            collection, scope="agent_data", agent_uid=agent_uid, days_to_keep=days)
        if type(output) == bool and output == False:
            status = "failure"
            ret_code = 500
            count_deleted = 0
        else:
            status = "success"
            count_deleted = int(output)
        return jsonify(
            {
                'deleted_count': count_deleted,
                'status': status,
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code


@app.route('/siaas-server/agents/configs', methods=['GET'], strict_slashes=False)
def agents_configs():
    """
    Server API route - agents published configs
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    collection = get_db_collection()
    merge_broadcast = request.args.get('merge_broadcast', default=0, type=int)
    output = siaas_aux.get_dict_current_agent_configs(
        collection, merge_broadcast=merge_broadcast)
    if type(output) == bool and output == False:
        status = "failure"
        ret_code = 500
        output = {}
    else:
        status = "success"
    return jsonify(
        {
            'output': output,
            'status': status,
            'total_entries': len(output),
            'time': siaas_aux.get_now_utc_str()
        }
    ), ret_code


@app.route('/siaas-server/agents/configs/<agent_uid>', methods=['GET', 'POST', 'DELETE'], strict_slashes=False)
def agents_configs_id(agent_uid):
    """
    Server API route - agents published configs (specific UIDs, comma-separated)
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    collection = get_db_collection()
    if request.method == 'GET':
        merge_broadcast = request.args.get(
            'merge_broadcast', default=0, type=int)
        output = siaas_aux.get_dict_current_agent_configs(
            collection, agent_uid=agent_uid, merge_broadcast=merge_broadcast)
        if type(output) == bool and output == False:
            status = "failure"
            ret_code = 500
            output = {}
        else:
            status = "success"
        return jsonify(
            {
                'output': output,
                'status': status,
                'total_entries': len(output),
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code
    if request.method == 'POST':
        content = request.json
        output = siaas_aux.create_or_update_agent_configs(
            collection, agent_uid=agent_uid, config_dict=content, orig_ip=ip)
        if output:
            status = "success"
        else:
            status = "failure"
            ret_code = 500
        return jsonify(
            {
                'status': status,
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code
    if request.method == 'DELETE':
        output = siaas_aux.delete_all_records_older_than(
            collection, scope="agent_configs", agent_uid=agent_uid, days_to_keep=0)
        if type(output) == bool and output == False:
            status = "failure"
            ret_code = 500
            count_deleted = 0
        else:
            status = "success"
            count_deleted = int(output)
        return jsonify(
            {
                'deleted_count': count_deleted,
                'status': status,
                'time': siaas_aux.get_now_utc_str()
            }
        ), ret_code


@app.route('/siaas-server/agents/history', methods=['GET'], strict_slashes=False)
def agents_history():
    """
    Server API route - agents historical data
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    module = request.args.get('module', default='*', type=str)
    # less than 1 equates to having no output limit
    limit_outputs = request.args.get('limit', default=100, type=int)
    days = request.args.get('days', default=15, type=int)
    sort_by = request.args.get('sort', default="date", type=str)
    older_first = request.args.get('older', default=0, type=int)
    hide_empty = request.args.get('hide', default=0, type=int)
    for m in module.split(','):
        if m.strip() == "*":
            module = None
    collection = get_db_collection()
    if limit_outputs < 0:
        limit_outputs = 0  # a negative value makes MongoDB behave differently. Let's avoid that
    output = siaas_aux.get_dict_history_agent_data(
        collection, module=module, limit_outputs=limit_outputs, days=days, sort_by=sort_by, older_first=older_first, hide_empty=hide_empty)
    if type(output) == bool and output == False:
        status = "failure"
        ret_code = 500
        output = {}
    else:
        status = "success"

    return jsonify(
        {
            'output': output,
            'status': status,
            'total_entries': len(output),
            'time': siaas_aux.get_now_utc_str()
        }
    ), ret_code


@app.route('/siaas-server/agents/history/<agent_uid>', methods=['GET'], strict_slashes=False)
def agents_history_id(agent_uid):
    """
    Server API route - agents historical data (specific UIDs, comma-separated)
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    ret_code = 200
    module = request.args.get('module', default='*', type=str)
    # less than 1 equates to having no output limit
    limit_outputs = request.args.get('limit', default=100, type=int)
    days = request.args.get('days', default=15, type=int)
    sort_by = request.args.get('sort', default="date", type=str)
    older_first = request.args.get('older', default=0, type=int)
    hide_empty = request.args.get('hide', default=0, type=int)
    for m in module.split(','):
        if m.strip() == "*":
            module = None
    collection = get_db_collection()
    if limit_outputs < 0:
        limit_outputs = 0  # a negative value makes MongoDB behave differently. Let's avoid that
    output = siaas_aux.get_dict_history_agent_data(
        collection, agent_uid=agent_uid, module=module, limit_outputs=limit_outputs, days=days, sort_by=sort_by, older_first=older_first, hide_empty=hide_empty)
    if type(output) == bool and output == False:
        status = "failure"
        ret_code = 500
        output = {}
    else:
        status = "success"
    return jsonify(
        {
            'output': output,
            'status': status,
            'total_entries': len(output),
            'time': siaas_aux.get_now_utc_str()
        }
    ), ret_code
