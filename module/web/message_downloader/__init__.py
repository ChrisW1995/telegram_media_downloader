# -*- coding: utf-8 -*-
"""Message Downloader main module

Handles /message_downloader and related page routes
"""

from flask import Blueprint, render_template, redirect, url_for, request, session
from loguru import logger

# Create main Blueprint
bp = Blueprint('message_downloader', __name__)


@bp.route("/message_downloader")
def message_downloader():
    """Message Downloader main page"""
    # Check message_downloader authentication status
    if not session.get('message_downloader_authenticated', False):
        # Store original request URL for redirect after login
        session['next_url'] = request.url
        return redirect(url_for('message_downloader.message_downloader_login'))

    return render_template("message_downloader.html")


@bp.route("/message_downloader/login")
def message_downloader_login():
    """Message Downloader login page"""
    # If already logged in, redirect to target page
    if session.get('message_downloader_authenticated', False):
        next_url = session.pop('next_url', url_for('message_downloader.message_downloader'))
        return redirect(next_url)

    return render_template("message_downloader_login.html")


def register_blueprints(flask_app, original_app=None):
    """Register all Message Downloader related Blueprints"""
    from . import auth, groups, downloads, thumbnails

    # Set the original app instance in all modules
    if original_app:
        auth.set_app_instance(original_app)
        groups.set_app_instance(original_app)
        downloads.set_app_instance(original_app)
        thumbnails.set_app_instance(original_app)

    # Register main Blueprint
    flask_app.register_blueprint(bp)

    # Register sub-module Blueprints
    flask_app.register_blueprint(auth.bp, url_prefix='/api/auth')
    flask_app.register_blueprint(groups.bp, url_prefix='/api/groups')
    flask_app.register_blueprint(downloads.bp, url_prefix='/api/fast_download')
    flask_app.register_blueprint(thumbnails.bp, url_prefix='/api/message_downloader_thumbnail')

    # Register ZIP download endpoints under /api/download
    # Create a separate blueprint instance for ZIP endpoints
    zip_bp = Blueprint('message_downloader_zip', __name__)
    zip_bp.add_url_rule('/zip', 'download_messages_as_zip', downloads.download_messages_as_zip, methods=['POST'])
    zip_bp.add_url_rule('/zip/status/<manager_id>', 'check_zip_download_status', downloads.check_zip_download_status, methods=['GET'])
    flask_app.register_blueprint(zip_bp, url_prefix='/api/download')

    # Register progress endpoint under /api (for compatibility with frontend)
    # Create a separate blueprint for progress API
    progress_bp = Blueprint('message_downloader_progress', __name__)
    progress_bp.add_url_rule('/download_progress', 'get_download_progress_api', downloads.get_download_progress_api, methods=['GET'])
    flask_app.register_blueprint(progress_bp, url_prefix='/api')

    logger.info("Message Downloader blueprints registered successfully")