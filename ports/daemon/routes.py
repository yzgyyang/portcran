"""WebAPI routes for Flask."""
from typing import List
from flask import Flask, Response, abort, jsonify, url_for
from .models import Json, Port


def define_routes(app: Flask) -> None:
    """Define the WebAPI routes."""
    def as_json(port: Port) -> Json:
        json = port.as_json()
        json["uri"] = url_for('get_port', port_id=json.pop('id'), external=True)
        return json

    @app.route('/api/ports/', methods=['GET'])
    def get_ports() -> Response:  # pylint: disable=W0612
        ports: List[Json] = []
        for port in Port.query.all():
            ports.append(as_json(port))
        return jsonify(ports)

    @app.route('/api/ports/<port_id:int>', methods=['GET'])
    def get_port(port_id: int) -> Response:  # pylint: disable=W0612
        ports = Port.query.filter_by(id=port_id)
        if not ports:
            abort(404)
        return ports.single()
