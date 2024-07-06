import os
import gridfs
import pika
import json
from flask import Flask, request, send_file, jsonify
from flask_pymongo import PyMongo
from auth import validate
from auth_svc import access
from storage import util
from bson.objectid import ObjectId
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

server = Flask(__name__)

# Set up MongoDB connections
server.config["MONGO_VIDEOS_URI"] = os.getenv('MONGODB_VIDEOS_URI')
mongo_video = PyMongo(server, uri=os.getenv('MONGODB_VIDEOS_URI'))

server.config["MONGO_MP3S_URI"] = os.getenv('MONGODB_MP3S_URI')
mongo_mp3 = PyMongo(server, uri=os.getenv('MONGODB_MP3S_URI'))

fs_videos = gridfs.GridFS(mongo_video.db)
fs_mp3s = gridfs.GridFS(mongo_mp3.db)

# RabbitMQ connection
rabbitmq_host = os.getenv('RABBITMQ_HOST')
try:
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host, heartbeat=0))
    channel = connection.channel()
except Exception as e:
    print(f"Failed to connect to RabbitMQ server: {e}")
    exit(1)

@server.route("/login", methods=["POST"])
def login():
    token, err = access.login(request)

    if not err:
        return jsonify({"token": token}), 200  # Return token with 200 OK status
    else:
        return jsonify({"error": err}), 401  # Return error message with 401 Unauthorized status

@server.route("/upload", methods=["POST"])
def upload():
    if "Authorization" not in request.headers:
        return jsonify({"error": "Unauthorized"}), 401

    auth_header = request.headers["Authorization"]
    token = auth_header.split()[1]

    print(f"JWT Token: {token}")

    access_info, err = validate.token(request)

    if err:
        print(f"Token validation error: {err}")
        return jsonify({"error": err}), 401

    try:
        access = json.loads(access_info)
    except json.JSONDecodeError as e:
        print(f"Error decoding access JSON: {e}")
        return jsonify({"error": "Invalid token format"}), 401

    if not access["admin"]:
        return jsonify({"error": "Unauthorized, admin role required"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    err = util.upload(file, fs_videos, channel, access)

    if err:
        print(f"Upload error: {err}")
        return jsonify({"error": err}), 500

    return jsonify({"message": "File uploaded successfully"}), 200

@server.route("/download", methods=["GET"])
def download():
    if "Authorization" not in request.headers:
        return jsonify({"error": "Unauthorized"}), 401

    auth_header = request.headers["Authorization"]
    token = auth_header.split()[1]

    print(f"JWT Token: {token}")

    access_info, err = validate.token(request)

    if err:
        print(f"Token validation error: {err}")
        return jsonify({"error": err}), 401

    try:
        access = json.loads(access_info)
    except json.JSONDecodeError as e:
        print(f"Error decoding access JSON: {e}")
        return jsonify({"error": "Invalid token format"}), 401

    if not access["admin"]:
        return jsonify({"error": "Unauthorized, admin role required"}), 403

    fid_string = request.args.get("fid")

    if not fid_string:
        return jsonify({"error": "fid is required"}), 400

    try:
        out = fs_mp3s.get(ObjectId(fid_string))
        return send_file(out, download_name=f"{fid_string}.mp3")
    except Exception as err:
        print(err)
        return jsonify({"error": "internal server error"}), 500

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8080)
