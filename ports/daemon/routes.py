"""WebAPI routes for Flask."""
from typing import List
from flask import Response, abort, jsonify, url_for
from .models import Json, Port
from . import bp


def as_json(port: Port) -> Json:
    """Convert the specified Port into a JSON structure."""
    json = port.as_json()
    json["uri"] = url_for('portd.get_port', port_id=json.pop('id'), external=True)
    return json


@bp.route('/api/ports/', methods=['GET'])
def get_ports() -> Response:
    """Get all the available ports."""
    ports: List[Json] = []
    for port in Port.query.all():
        ports.append(as_json(port))
    return jsonify(ports)


@bp.route('/api/ports/<int:port_id>', methods=['GET'])
def get_port(port_id: int) -> Response:
    """Get a port by the specified port identification number."""
    ports = Port.query.filter_by(id=port_id)
    if not ports:
        abort(404)
    return ports.single()
