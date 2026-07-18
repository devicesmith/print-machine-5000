from flask import Flask, request, jsonify
import json
from datetime import datetime
from escpos.printer import File
import requests
from io import BytesIO
from PIL import Image, ImageOps, ImageEnhance

app = Flask(__name__)

PRINTER_PATH = "/dev/usb/lp0"
PRINTER_WIDTH_PX = 576
USER_AGENT = "Mozilla/5.0 (compatible; ReceiptPrinter/1.0)"


def get_printer():
    try:
        return File(PRINTER_PATH), None
    except FileNotFoundError:
        return None, f"Printer device not found at {PRINTER_PATH}"
    except PermissionError:
        return None, f"Permission denied accessing {PRINTER_PATH}. Check user is in 'lp' group."
    except Exception as e:
        return None, f"Failed to open printer: {str(e)}"


def format_timestamp(dt: datetime) -> str:
    return dt.strftime("%B %d, %Y at %I:%M:%S %p")


def prepare_image_for_thermal(image: Image.Image, max_width: int) -> Image.Image:
    image = image.convert("RGB")

    width, height = image.size
    if width > max_width:
        new_height = int((max_width / width) * height)
        image = image.resize((max_width, new_height), Image.LANCZOS)

    image = ImageOps.grayscale(image)

    contrast = ImageEnhance.Contrast(image)
    image = contrast.enhance(1.15)

    brightness = ImageEnhance.Brightness(image)
    image = brightness.enhance(1.08)

    return image


def send_beep(printer, n=3, t=2):
    try:
        printer._raw(bytes([0x1B, 0x42, n, t]))
    except Exception:
        pass


def print_image_from_url(printer, image_url):
    if not image_url or image_url == "N/A":
        return

    try:
        headers = {
            "User-Agent": USER_AGENT
        }
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()

        image_data = BytesIO(response.content)
        image = Image.open(image_data)
        image = prepare_image_for_thermal(image, PRINTER_WIDTH_PX)

        printer.set(align="center")
        printer.image(image)
        printer.set(align="left")

    except requests.exceptions.Timeout:
        printer.text("image load timed out\n")
    except requests.exceptions.HTTPError as e:
        printer.text(f"image unavailable: {e}\n")
    except Exception as e:
        printer.text(f"could not print image: {str(e)}\n")


def print_submission(data: dict, timestamp: str):
    printer, error = get_printer()
    if not printer:
        raise RuntimeError(error)

    try:
        printer.set(align="left")
        printer.text("Timestamp:\n")
        printer.text(f"{timestamp}\n")

        printer.text("\n")
        printer.text("Name:\n")
        printer.text(f"{data.get('Name', 'N/A')}\n")

        printer.text("\n")
        printer.text("Image:\n")
        print_image_from_url(printer, data.get('Image URL', 'N/A'))

        printer.text("\n")
        printer.text("Message:\n")
        printer.text(f"{data.get('Message', 'N/A')}\n")

        printer.text("\n")
        send_beep(printer, n=3, t=2)
        printer.cut()
    finally:
        printer.close()


@app.route('/form-submit', methods=['POST'])
def handle_form():
    try:
        form_data = request.form.to_dict()

        if not form_data:
            form_data = request.get_json(silent=True)

        now = datetime.now()
        formatted_timestamp = format_timestamp(now)

        submission = {
            'timestamp': formatted_timestamp,
            'data': form_data or {},
            'headers': dict(request.headers),
            'ip': request.remote_addr
        }

        print("=== Form Submission Received ===")
        print(json.dumps(submission, indent=2))

        try:
            print_submission(submission['data'], submission['timestamp'])
            print("=== Printed Successfully ===")
        except RuntimeError as e:
            print(f"Printer error: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Printer error: {str(e)}'}), 503
        except Exception as e:
            print(f"Unexpected printer error: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Failed to print submission'}), 500

        return jsonify({'status': 'success', 'message': 'Received and printed'}), 200

    except Exception as e:
        print("Error:", str(e))
        return jsonify({'status': 'error'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
