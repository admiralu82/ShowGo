"""Image processing utilities for ShowGo."""
from PIL import Image
from flask import current_app
import os


def is_animated_gif(image_path):
    """Check if an image is an animated GIF."""
    try:
        with Image.open(image_path) as img:
            return getattr(img, 'is_animated', False) and img.format == 'GIF'
    except Exception:
        return False


def get_image_dimensions(image_path):
    """Get the dimensions of an image."""
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        return None


def should_resize_image(width, height, max_resolution):
    """Check if image should be resized based on max resolution."""
    max_width, max_height = max_resolution
    return width > max_width or height > max_height


def resize_image(image_path, max_resolution, output_path=None):
    """
    Resize an image to fit within max_resolution while maintaining aspect ratio.
    Returns (success, new_dimensions).
    """
    try:
        with Image.open(image_path) as img:
            # Don't process animated GIFs
            if is_animated_gif(image_path):
                return False, img.size

            # Calculate new dimensions
            max_width, max_height = max_resolution
            width, height = img.size
            if not should_resize_image(width, height, max_resolution):
                return False, (width, height)

            # Calculate aspect ratio
            aspect = width / height
            if width > max_width:
                width = max_width
                height = int(width / aspect)
            if height > max_height:
                height = max_height
                width = int(height * aspect)

            # Perform resize
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            
            # Save if output path provided
            if output_path:
                resized.save(output_path, quality=95, optimize=True)
                return True, (width, height)
            else:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
                img.save(image_path, quality=95, optimize=True)
                return True, (width, height)

    except Exception as e:
        print(f"Error resizing image {image_path}: {e}")
        return False, None



def process_image(image_path, max_resolution=None, convert_webp=None):
    """
    Process an image according to configuration settings.
    Returns (success, warnings).
    """
    warnings = []
    
    # Skip processing for animated GIFs
    if is_animated_gif(image_path):
        return True, ["Animated GIF detected - skipping processing"]

    # Get current dimensions
    dimensions = get_image_dimensions(image_path)
    if not dimensions:
        return False, ["Failed to read image dimensions"]
    width, height = dimensions

    # Check for low resolution
    vga_width, vga_height = current_app.config['VGA_RESOLUTION']
    if width < vga_width or height < vga_height:
        msg = (
            f"Low resolution image detected: {width}x{height} "
            f"(below {vga_width}x{vga_height})"
        )
        warnings.append(msg)

    # Handle resizing if needed
    if max_resolution is None:
        max_res_key = current_app.config['DEFAULT_MAX_RESOLUTION']
        max_resolution = current_app.config['MAX_IMAGE_RESOLUTIONS'][max_res_key]

    if should_resize_image(width, height, max_resolution):
        success, new_dims = resize_image(image_path, max_resolution)
        if success and new_dims:
            msg = (
                f"Image resized from {width}x{height} "
                f"to {new_dims[0]}x{new_dims[1]}"
            )
            warnings.append(msg)
        elif not success:
            return False, ["Failed to resize image"]

    # Handle WebP conversion if enabled

    return True, warnings 