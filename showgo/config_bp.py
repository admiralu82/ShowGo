# showgo/config_bp.py
# Blueprint for configuration pages and actions

import os
import traceback
import uuid
from datetime import datetime, timezone # Import datetime and timezone
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, make_response, current_app, send_from_directory)
from werkzeug.exceptions import RequestEntityTooLarge

# Import extensions, models, utils from the application package (.)
from .extensions import db
from .models import MediaFile, Setting
from .utils import (get_setting, save_setting, initialize_database,
                    get_database_media, find_missing_media_files,
                    find_unexpected_items, cleanup_unexpected_items,
                    remove_missing_media_db_entries,
                    allowed_file, generate_thumbnail, get_media_type,
                    is_web_friendly_video)
from .config import DEFAULT_SETTINGS_DB # Import defaults for fallback
from .image_processing import process_image

# Create Blueprint
config_bp = Blueprint('config_bp', __name__)

# --- Helper to update media timestamp ---
def _touch_media_timestamp():
    """Updates the media_last_changed setting to the current time."""
    try:
        now_ts = datetime.now(timezone.utc).timestamp()
        save_setting('media_last_changed', now_ts)
    except Exception as e:
        print(f"ERROR: Failed to update media_last_changed timestamp: {e}")

# --- Helper to update general config timestamp (used by settings and logo upload) ---
def _touch_config_timestamp():
    """Touches a general configuration setting to update its last_updated timestamp."""
    try:
        current_value = get_setting('overlay_enabled', False)
        save_setting('overlay_enabled', current_value)
        print(f"Touched general config timestamp by re-saving 'overlay_enabled'.")
    except Exception as e:
        print(f"ERROR: Failed to touch general config timestamp: {e}")


# --- Routes ---

@config_bp.route('/')
def config_redirect():
    """Redirects base blueprint route to the general settings page."""
    return redirect(url_for('.config_general'))


@config_bp.route('/general', methods=['GET', 'POST'])
def config_general():
    """Displays and handles saving of general slideshow/widget/display settings."""
    if request.method == 'POST':
        # ... (POST logic remains the same as the previous version) ...
        settings_saved_successfully = True
        try:
            # Slideshow General Settings
            allowed_transitions = ['fade', 'slide', 'kenburns']
            transition = request.form.get('transition_effect', DEFAULT_SETTINGS_DB['slideshow_transition_effect'])
            if transition not in allowed_transitions:
                flash(f"Invalid transition effect '{transition}'. Defaulting.", "warning")
                transition = DEFAULT_SETTINGS_DB['slideshow_transition_effect']
            settings_saved_successfully &= save_setting('slideshow_transition_effect', transition)
            settings_saved_successfully &= save_setting('slideshow_duration_seconds', int(request.form.get('duration_seconds', DEFAULT_SETTINGS_DB['slideshow_duration_seconds'])))
            settings_saved_successfully &= save_setting('slideshow_image_order', request.form.get('image_order', DEFAULT_SETTINGS_DB['slideshow_image_order']))
            settings_saved_successfully &= save_setting('slideshow_image_scaling', request.form.get('image_scaling', DEFAULT_SETTINGS_DB['slideshow_image_scaling']))
            # Video Settings (General)
            settings_saved_successfully &= save_setting('slideshow_video_scaling', request.form.get('video_scaling', DEFAULT_SETTINGS_DB['slideshow_video_scaling']))
            settings_saved_successfully &= save_setting('slideshow_video_autoplay', 'video_autoplay' in request.form)
            settings_saved_successfully &= save_setting('slideshow_video_loop', 'video_loop' in request.form)
            settings_saved_successfully &= save_setting('slideshow_video_muted', 'video_muted' in request.form)
            settings_saved_successfully &= save_setting('slideshow_video_show_controls', 'video_show_controls' in request.form)
            
            # Video Playback Advanced Settings
            duration_limit_enabled = request.form.get('video_duration_limit_enabled') == 'on'
            duration_limit_seconds = int(request.form.get('video_duration_limit_seconds', 30))
            random_start_enabled = request.form.get('video_random_start_enabled') == 'on'

            # Validate duration limit
            if duration_limit_seconds < 1:
                duration_limit_seconds = 1
            elif duration_limit_seconds > 3600:
                duration_limit_seconds = 3600

            # If duration limit is disabled, ensure random start is also disabled
            if not duration_limit_enabled:
                random_start_enabled = False

            settings_saved_successfully &= save_setting('slideshow_video_duration_limit_enabled', duration_limit_enabled)
            settings_saved_successfully &= save_setting('slideshow_video_duration_limit_seconds', duration_limit_seconds)
            settings_saved_successfully &= save_setting('slideshow_video_random_start_enabled', random_start_enabled)

            # Overlay Branding Settings
            settings_saved_successfully &= save_setting('overlay_enabled', 'overlay_enabled' in request.form)
            settings_saved_successfully &= save_setting('overlay_text', request.form.get('overlay_text', DEFAULT_SETTINGS_DB['overlay_text']))
            settings_saved_successfully &= save_setting('overlay_position', request.form.get('overlay_position', DEFAULT_SETTINGS_DB['overlay_position']))
            settings_saved_successfully &= save_setting('overlay_font_size', request.form.get('overlay_font_size', DEFAULT_SETTINGS_DB['overlay_font_size']))
            settings_saved_successfully &= save_setting('overlay_font_color', request.form.get('overlay_font_color', DEFAULT_SETTINGS_DB['overlay_font_color']))
            settings_saved_successfully &= save_setting('overlay_logo_enabled', 'overlay_logo_enabled' in request.form)
            allowed_display_modes = ['text_only', 'logo_only', 'logo_and_text_side', 'logo_and_text_below']
            display_mode = request.form.get('overlay_display_mode', DEFAULT_SETTINGS_DB['overlay_display_mode'])
            if display_mode not in allowed_display_modes:
                display_mode = DEFAULT_SETTINGS_DB['overlay_display_mode']
            settings_saved_successfully &= save_setting('overlay_display_mode', display_mode)
            settings_saved_successfully &= save_setting('overlay_background_color', request.form.get('overlay_background_color', DEFAULT_SETTINGS_DB['overlay_background_color']))
            settings_saved_successfully &= save_setting('overlay_padding', request.form.get('overlay_padding', DEFAULT_SETTINGS_DB['overlay_padding']))
            # Widget Settings
            settings_saved_successfully &= save_setting('widgets_time_enabled', 'time_widget_enabled' in request.form)
            # Burn-in Settings
            settings_saved_successfully &= save_setting('burn_in_prevention_enabled', 'burn_in_prevention_enabled' in request.form)
            settings_saved_successfully &= save_setting('burn_in_prevention_elements', request.form.getlist('burn_in_elements'))
            settings_saved_successfully &= save_setting('burn_in_prevention_interval_seconds', int(request.form.get('burn_in_interval_seconds', DEFAULT_SETTINGS_DB['burn_in_prevention_interval_seconds'])))
            settings_saved_successfully &= save_setting('burn_in_prevention_strength_pixels', int(request.form.get('burn_in_strength_pixels', DEFAULT_SETTINGS_DB['burn_in_prevention_strength_pixels'])))

            if settings_saved_successfully:
                flash("Configuration saved successfully!", "success")
            else:
                flash("An error occurred while saving some settings. Check logs.", "error")
        except ValueError:
            flash("Invalid input value provided (e.g., duration, interval, strength must be numbers).", "error")
        except Exception as e:
            print(f"Error processing save settings request: {e}")
            traceback.print_exc()
            flash("An unexpected error occurred while saving settings.", "error")
        return redirect(url_for('.config_general'))

    # GET Request Logic
    defaults = DEFAULT_SETTINGS_DB
    # This current_config is for the form values (settings from DB)
    current_config_values = {
         "slideshow": {
             "duration_seconds": get_setting("slideshow_duration_seconds", defaults['slideshow_duration_seconds']),
             "transition_effect": get_setting("slideshow_transition_effect", defaults['slideshow_transition_effect']),
             "image_order": get_setting("slideshow_image_order", defaults['slideshow_image_order']),
             "image_scaling": get_setting("slideshow_image_scaling", defaults['slideshow_image_scaling']),
             "video_scaling": get_setting("slideshow_video_scaling", defaults['slideshow_video_scaling']),
             "video_autoplay": get_setting("slideshow_video_autoplay", defaults['slideshow_video_autoplay']),
             "video_loop": get_setting("slideshow_video_loop", defaults['slideshow_video_loop']),
             "video_muted": get_setting("slideshow_video_muted", defaults['slideshow_video_muted']),
             "video_show_controls": get_setting("slideshow_video_show_controls", defaults['slideshow_video_show_controls']),
         },
         "overlay": {
             "enabled": get_setting("overlay_enabled", defaults['overlay_enabled']),
             "text": get_setting("overlay_text", defaults['overlay_text']),
             "position": get_setting("overlay_position", defaults['overlay_position']),
             "font_size": get_setting("overlay_font_size", defaults['overlay_font_size']),
             "font_color": get_setting("overlay_font_color", defaults['overlay_font_color']),
             "logo_enabled": get_setting("overlay_logo_enabled", defaults['overlay_logo_enabled']),
             "display_mode": get_setting("overlay_display_mode", defaults['overlay_display_mode']),
             "background_color": get_setting("overlay_background_color", defaults['overlay_background_color']),
             "padding": get_setting("overlay_padding", defaults['overlay_padding']),
         },
         "widgets": {
             "time": {"enabled": get_setting("widgets_time_enabled", defaults['widgets_time_enabled'])}
         },
         "burn_in_prevention": {
             "enabled": get_setting("burn_in_prevention_enabled", defaults['burn_in_prevention_enabled']),
             "elements": get_setting("burn_in_prevention_elements", defaults['burn_in_prevention_elements']),
             "interval_seconds": get_setting("burn_in_prevention_interval_seconds", defaults['burn_in_prevention_interval_seconds']),
             "strength_pixels": get_setting("burn_in_prevention_strength_pixels", defaults['burn_in_prevention_strength_pixels'])
         },
    }

    # Video Playback Settings (for the separate form that will be moved here)
    video_duration_limit_enabled = get_setting('slideshow_video_duration_limit_enabled', defaults.get('slideshow_video_duration_limit_enabled', False))
    video_duration_limit_seconds = get_setting('slideshow_video_duration_limit_seconds', defaults.get('slideshow_video_duration_limit_seconds', 30))
    video_random_start_enabled = get_setting('slideshow_video_random_start_enabled', defaults.get('slideshow_video_random_start_enabled', False))

    logo_path = os.path.join(current_app.config['ASSETS_FOLDER'], current_app.config['OVERLAY_LOGO_FILENAME'])
    logo_exists = os.path.isfile(logo_path)

    return render_template('config_general.html',
                           settings=current_config_values,
                           video_duration_limit_enabled=video_duration_limit_enabled,
                           video_duration_limit_seconds=video_duration_limit_seconds,
                           video_random_start_enabled=video_random_start_enabled,
                           logo_exists=logo_exists,
                           APP_CONFIG_OVERLAY_LOGO_FILENAME=current_app.config['OVERLAY_LOGO_FILENAME'],
                           active_page='general')

@config_bp.route('/upload_overlay_logo', methods=['POST'])
def upload_overlay_logo():
    # ... (content remains the same)
    if 'overlay_logo_file' not in request.files:
        flash('No logo file part in the request.', 'error')
        return redirect(url_for('.config_general'))
    file = request.files['overlay_logo_file']
    if file.filename == '':
        flash('No selected logo file.', 'error')
        return redirect(url_for('.config_general'))
    if file and file.filename.rsplit('.', 1)[1].lower() == 'png':
        filename = current_app.config['OVERLAY_LOGO_FILENAME']
        assets_folder = current_app.config['ASSETS_FOLDER']
        save_path = os.path.join(assets_folder, filename)
        try:
            os.makedirs(assets_folder, exist_ok=True)
            file.save(save_path)
            flash('Overlay logo uploaded successfully!', 'success')
            _touch_config_timestamp()
        except Exception as e:
            print(f"Error saving overlay logo: {e}")
            traceback.print_exc()
            flash('Error saving overlay logo.', 'error')
    else:
        flash('Invalid file type for logo. Please upload a PNG file.', 'error')
    return redirect(url_for('.config_general'))

@config_bp.route('/media', methods=['GET', 'POST'])
def config_media():
    """Media management configuration page."""
    if request.method == 'POST':
        # Handle form submission
        max_resolution = request.form.get('max_resolution', DEFAULT_SETTINGS_DB['max_resolution'])
        convert_to_webp = False
        webp_quality = 80

        # Validate WebP quality
        if webp_quality < 1 or webp_quality > 100:
            flash('WebP quality must be between 1 and 100', 'error')
            return redirect(url_for('config_bp.config_media'))

        # Save settings
        save_setting('max_resolution', max_resolution)
        save_setting('convert_to_webp', convert_to_webp)
        save_setting('webp_quality', webp_quality)

        flash('Media settings saved successfully', 'success')
        return redirect(url_for('config_bp.config_media'))

    # Get all media files from database
    all_media, db_uuids = get_database_media()
    
    # Check for missing files
    missing_db_entries = find_missing_media_files(all_media)
    
    # Check for unexpected items
    orphaned_uuid_files, unexpected_files, unexpected_dirs = find_unexpected_items(db_uuids)

    # Load current settings for display
    current_config = {
        # Media settings from database
        'max_resolution': get_setting('max_resolution'),
        'convert_to_webp': get_setting('convert_to_webp'),
        'webp_quality': get_setting('webp_quality'),
        
        # App configuration values
        'MAX_CONTENT_LENGTH': current_app.config['MAX_CONTENT_LENGTH'],
        'MAX_IMAGE_RESOLUTIONS': current_app.config['MAX_IMAGE_RESOLUTIONS'],
        'THUMBNAIL_SIZE': current_app.config['THUMBNAIL_SIZE'],
        'THUMBNAIL_FORMAT': current_app.config['THUMBNAIL_FORMAT'],
        'THUMBNAIL_EXT': current_app.config['THUMBNAIL_EXT'],
        'ALLOWED_EXTENSIONS': current_app.config['ALLOWED_EXTENSIONS'],
        'ALLOWED_IMAGE_EXTENSIONS': current_app.config['ALLOWED_IMAGE_EXTENSIONS'],
        'ALLOWED_VIDEO_EXTENSIONS': current_app.config['ALLOWED_VIDEO_EXTENSIONS'],
        'UPLOAD_FOLDER': current_app.config['UPLOAD_FOLDER'],
        'THUMBNAIL_FOLDER': current_app.config['THUMBNAIL_FOLDER']
    }

    return render_template('config_media.html',
                         config=current_config,
                         media_files=all_media,
                         missing_db_entries=missing_db_entries,
                         orphaned_uuid_files=orphaned_uuid_files,
                         unexpected_files=unexpected_files,
                         unexpected_dirs=unexpected_dirs,
                         active_page='media')

@config_bp.route('/upload', methods=['POST'])
def upload_media():
    """Handle media file uploads with image processing."""
    pil_available = current_app.config.get('PIL_AVAILABLE', False)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    thumbnail_folder = current_app.config['THUMBNAIL_FOLDER']
    thumbnail_size = current_app.config.get('THUMBNAIL_SIZE', (150, 150))
    thumbnail_format = current_app.config.get('THUMBNAIL_FORMAT', 'PNG')
    thumbnail_ext = f".{thumbnail_format.lower()}"
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 512*1024*1024)
    max_size_mb = max_size // 1024 // 1024

    if not pil_available:
        flash("Внимание: Библиотека обработки изображений (Pillow) не установлена.", "warning")

    if 'media_files' not in request.files:
        flash('В запросе нет части файла.', 'error')
        return redirect(url_for('.config_media'))

    files = request.files.getlist('media_files')
    uploaded_count = 0
    error_count = 0
    thumb_error_count = 0
    media_changed = False
    processing_warnings = []

    if not files or files[0].filename == '':
        flash('Не выбран файл.', 'error')
        return redirect(url_for('.config_media'))

    for file in files:
        if file and allowed_file(file.filename):
            # Keep original filename with Unicode characters (Russian, etc.)
            original_filename = file.filename
            
            # Safely extract extension
            if '.' not in original_filename:
                flash(f'Файл "{original_filename}" не имеет расширения.', 'error')
                error_count += 1
                continue
            
            file_ext = original_filename.rsplit('.', 1)[1].lower()
            uuid_hex = uuid.uuid4().hex
            disk_filename = f"{uuid_hex}.{file_ext}"
            media_type = get_media_type(original_filename)

            if not media_type:
                flash(f"Тип файла {original_filename} не распознан.", "error")
                error_count += 1
                continue

            try:
                # Save the uploaded file
                file.save(os.path.join(upload_folder, disk_filename))

                # Process videos
                if media_type == 'video':
                    if not is_web_friendly_video(os.path.join(upload_folder, disk_filename)):
                        flash(
                            f"Видео '{original_filename}' содержит неподдерживаемые "
                            "форматы. Пожалуйста, используйте веб-дружественные форматы.", "error"
                        )
                        error_count += 1
                        if os.path.exists(os.path.join(upload_folder, disk_filename)):
                            try:
                                os.remove(os.path.join(upload_folder, disk_filename))
                            except OSError as e:
                                print(f"Error cleaning up video: {e}")
                        continue

                # Process images
                elif media_type == 'image' and pil_available:
                    success, warnings = process_image(os.path.join(upload_folder, disk_filename))
                    if not success:
                        flash(
                            f"Не удалось обработать изображение {original_filename}.",
                            "error"
                        )
                        error_count += 1
                        if os.path.exists(os.path.join(upload_folder, disk_filename)):
                            try:
                                os.remove(os.path.join(upload_folder, disk_filename))
                            except OSError:
                                pass
                        continue
                    
                    # Add any processing warnings to our collection
                    if warnings:
                        processing_warnings.extend([
                            f"{original_filename}: {warning}"
                            for warning in warnings
                        ])

                # Generate thumbnail
                thumb_disk_filename = f"{uuid_hex}{thumbnail_ext}"
                thumb_dest_path = os.path.join(
                    thumbnail_folder,
                    thumb_disk_filename
                )
                thumb_success, _ = generate_thumbnail(
                    os.path.join(upload_folder, disk_filename),
                    thumb_dest_path,
                    thumbnail_size,
                    media_type
                )

                if not thumb_success:
                    if media_type == 'image':
                        thumb_error_count += 1
                        print(
                            f"Внимание: Не удалось сгенерировать миниатюру "
                            f"для изображения {original_filename}"
                        )
                    elif media_type == 'video':
                        print(
                            f"Информация: Не удалось сгенерировать миниатюру "
                            f"для видео {original_filename}"
                        )

                # Add to database
                display_name_default = os.path.splitext(original_filename)[0]
                new_media = MediaFile(
                    uuid_filename=uuid_hex,
                    original_filename=original_filename,
                    display_name=display_name_default,
                    extension=file_ext,
                    media_type=media_type
                )
                db.session.add(new_media)
                db.session.commit()
                uploaded_count += 1
                media_changed = True

            except RequestEntityTooLarge as e:
                print(f"Upload failed for {original_filename}: {e}")
                db.session.rollback()
                if os.path.exists(os.path.join(upload_folder, disk_filename)):
                    try:
                        os.remove(os.path.join(upload_folder, disk_filename))
                    except OSError:
                        pass
                error_count += 1
                break

            except Exception as e:
                print(f"Error processing file {original_filename}: {e}")
                traceback.print_exc()
                flash(f'Ошибка при обработке файла {original_filename}.', 'error')
                error_count += 1
                db.session.rollback()
                if os.path.exists(os.path.join(upload_folder, disk_filename)):
                    try:
                        os.remove(os.path.join(upload_folder, disk_filename))
                    except OSError:
                        pass

        elif file and file.filename != '':
            flash(f'Тип файла {file.filename} не разрешен.',
                 'error')
            error_count += 1

    if media_changed:
        _touch_media_timestamp()

    if uploaded_count > 0:
        flash(f'Успешно обработано {uploaded_count} файл(ов).',
              'success')

    if processing_warnings:
        for warning in processing_warnings:
            flash(warning, 'warning')

    if thumb_error_count > 0:
        flash(f'Не удалось сгенерировать {thumb_error_count} миниатюр.',
              'warning')

    if error_count > 0:
        flash(f'Не удалось обработать {error_count} файл(ов).', 'error')

    return redirect(url_for('.config_media'))

@config_bp.route('/delete', methods=['POST'])
def delete_media():
    media_ids_to_delete = request.form.getlist('selected_media')
    deleted_count = 0; error_count = 0; media_changed = False
    if not media_ids_to_delete: flash("Не выбрано ни одного файла для удаления.", "warning"); return redirect(url_for('.config_media'))
    upload_folder = current_app.config['UPLOAD_FOLDER']; thumbnail_folder = current_app.config['THUMBNAIL_FOLDER']
    for media_id in media_ids_to_delete:
        try:
            media_id_int = int(media_id); media_record = db.session.get(MediaFile, media_id_int)
            if media_record:
                disk_filename = media_record.get_disk_filename(); thumbnail_filename = media_record.get_thumbnail_filename(); original_path = os.path.join(upload_folder, disk_filename); thumbnail_path = os.path.join(thumbnail_folder, thumbnail_filename)
                try:
                    if os.path.isfile(original_path): os.remove(original_path)
                    else: print(f"Внимание: Оригинальный файл не найден при удалении: {original_path}")
                    if os.path.isfile(thumbnail_path): os.remove(thumbnail_path)
                except OSError as e: print(f"Error deleting files for media ID {media_id}: {e}"); flash(f"Ошибка при удалении файлов для '{media_record.display_name}', удаляем запись из БД anyway.", "warning")
                db.session.delete(media_record); deleted_count += 1; media_changed = True
            else: print(f"Media record not found in DB for ID: {media_id}"); error_count += 1
        except ValueError: print(f"Invalid media ID received: {media_id}"); error_count += 1
        except Exception as e: print(f"Error processing deletion for media ID {media_id}: {e}"); traceback.print_exc(); error_count += 1; db.session.rollback()
    try:
        if media_changed: db.session.commit(); _touch_media_timestamp()
        else: print("No media records found to delete, skipping commit and timestamp update.")
    except Exception as e: print(f"Error committing deletions to DB: {e}"); traceback.print_exc(); flash("Ошибка базы данных при коммите удаления.", "error"); db.session.rollback(); deleted_count = 0; error_count = len(media_ids_to_delete); media_changed=False
    if deleted_count > 0: flash(f"Успешно удалено {deleted_count} медиафайлов.", "success")
    if error_count > 0: flash(f"Произошла ошибка при удалении {error_count} медиафайлов. Проверьте логи.", "error")
    return redirect(url_for('.config_media'))

@config_bp.route('/cleanup/missing-db', methods=['POST'])
def cleanup_missing_media_db_route():
    media_ids = request.form.getlist('missing_media_ids')
    if not media_ids: flash("No missing media entries selected for removal.", "warning"); return redirect(url_for('.config_media'))
    print(f"Attempting to remove DB entries for missing media IDs: {media_ids}")
    deleted_count, error_count = remove_missing_media_db_entries(media_ids)
    if deleted_count > 0 and error_count == 0 : _touch_media_timestamp()
    elif deleted_count > 0: print("Partial success removing missing DB entries, timestamp likely updated.")
    if error_count > 0: flash(f"Removed {deleted_count} missing database entries, but encountered errors with {error_count} entries. Check logs.", "error")
    elif deleted_count > 0: flash(f"Successfully removed {deleted_count} database entries for missing media.", "success")
    else: flash("No database entries were removed (perhaps they were already gone?).", "info")
    return redirect(url_for('.config_media'))

@config_bp.route('/cleanup/unexpected-items', methods=['POST'])
def cleanup_unexpected_items_route():
    print("Starting unexpected items cleanup..."); items_to_delete = []
    _, db_uuids = get_database_media(); orphaned_uuid_files, unexpected_files, unexpected_dirs = find_unexpected_items(db_uuids)
    items_to_delete.extend(orphaned_uuid_files); items_to_delete.extend(unexpected_files); items_to_delete.extend(unexpected_dirs)
    if not items_to_delete: flash("No unexpected items found to clean up.", "info"); return redirect(url_for('.config_media'))
    print(f"Found {len(items_to_delete)} unexpected items to delete.")
    deleted_files, deleted_dirs, error_count = cleanup_unexpected_items(items_to_delete)
    deleted_items_msg = [];
    if deleted_files > 0: deleted_items_msg.append(f"{deleted_files} file(s)")
    if deleted_dirs > 0: deleted_items_msg.append(f"{deleted_dirs} director(y/ies)")
    if error_count > 0:
        if deleted_items_msg: flash(f"Deleted {' and '.join(deleted_items_msg)}, but encountered errors deleting {error_count} item(s). Check logs.", "error")
        else: flash(f"Cleanup failed. Encountered errors deleting {error_count} item(s). Check logs.", "error")
    elif deleted_items_msg: flash(f"Successfully deleted {' and '.join(deleted_items_msg)}.", "success")
    else: flash("Cleanup finished, but no items were deleted.", "warning")
    return redirect(url_for('.config_media'))

@config_bp.route('/update_image_settings', methods=['POST'])
def update_image_settings():
    """Update image processing settings."""
    try:
        # Get form data
        max_resolution = request.form.get('max_resolution', '1080p')
        convert_to_webp = False
        webp_quality = 80

        # Validate max resolution
        if max_resolution not in current_app.config['MAX_IMAGE_RESOLUTIONS']:
            flash('Invalid maximum resolution selected.', 'error')
            return redirect(url_for('.config_media'))

        # Validate WebP quality
        if not (1 <= webp_quality <= 100):
            flash('WebP quality must be between 1 and 100.', 'error')
            return redirect(url_for('.config_media'))

        # Save settings using the correct keys
        save_setting('max_resolution', max_resolution)
        save_setting('convert_to_webp', convert_to_webp)
        save_setting('webp_quality', webp_quality)

        flash('Image processing settings updated successfully.', 'success')

    except Exception as e:
        print(f"Error saving image settings: {e}")
        flash('Error saving image settings.', 'error')

    return redirect(url_for('.config_media'))

@config_bp.route('/update_video_settings', methods=['POST'])
def update_video_settings():
    """Update video playback settings."""
    try:
        # Get form data with defaults
        duration_limit_enabled = request.form.get('video_duration_limit_enabled') == 'on'
        duration_limit_seconds = int(request.form.get('video_duration_limit_seconds', 30))
        random_start_enabled = request.form.get('video_random_start_enabled') == 'on'

        # Validate duration limit
        if duration_limit_seconds < 1:
            duration_limit_seconds = 1
        elif duration_limit_seconds > 3600:
            duration_limit_seconds = 3600

        # If duration limit is disabled, ensure random start is also disabled
        if not duration_limit_enabled:
            random_start_enabled = False

        # Save each setting individually
        save_setting('slideshow_video_duration_limit_enabled', duration_limit_enabled)
        save_setting('slideshow_video_duration_limit_seconds', duration_limit_seconds)
        save_setting('slideshow_video_random_start_enabled', random_start_enabled)

        # Update last_changed timestamp for media
        _touch_media_timestamp()

        flash('Video playback settings updated successfully.', 'success')

    except Exception as e:
        current_app.logger.error(f"Error updating video settings: {str(e)}")
        flash('Error updating video playback settings.', 'error')

    return redirect(url_for('.config_general'))
