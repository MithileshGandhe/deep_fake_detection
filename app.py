"""
Deepfake Detection Web App - Backend (Flask)
============================================
Main application file. Contains:
  - Flask routes for serving pages and handling uploads
  - Dummy prediction function (ready to be swapped with a real ML model)
  - File validation and temporary storage logic
"""

import os
import uuid
import random
import time
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Max upload size: 100 MB
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# Folder where uploads are temporarily stored
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Allowed file extensions
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "mp4"}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def allowed_file(filename: str) -> bool:
    """Return True if the file extension is in the allowed list."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_type(filename: str) -> str:
    """Return 'image' or 'video' based on file extension."""
    ext = filename.rsplit(".", 1)[1].lower()
    return "video" if ext == "mp4" else "image"


# ---------------------------------------------------------------------------
# ⚡ PREDICTION FUNCTION — Replace this with your real ML model later
# ---------------------------------------------------------------------------

def predict_deepfake(file_path: str, file_type: str) -> dict:
    """
    Dummy prediction function.

    HOW TO REPLACE WITH A REAL MODEL:
    ----------------------------------
    1. Load your trained model (e.g., PyTorch, TensorFlow, ONNX) at startup
       using a global variable or a model registry.
    2. Preprocess the file (resize, normalize frames for video, etc.).
    3. Run inference and return the label + confidence score.

    Parameters
    ----------
    file_path : str
        Absolute path to the uploaded file.
    file_type : str
        'image' or 'video'

    Returns
    -------
    dict with keys:
        - label      : "REAL" or "FAKE"
        - confidence : float between 0.0 and 1.0
        - details    : human-readable explanation string
    """

    # --- DUMMY LOGIC (random result for demonstration) ---
    time.sleep(1.5)  # Simulate model inference latency

    confidence = round(random.uniform(0.60, 0.99), 2)
    label = random.choice(["REAL", "FAKE"])

    details = (
        f"{'Facial inconsistencies and GAN artifacts detected' if label == 'FAKE' else 'No manipulation artifacts found'}. "
        f"Analysis performed on {'video frames' if file_type == 'video' else 'image'}."
    )

    return {
        "label": label,
        "confidence": confidence,
        "details": details,
    }
    # --- END DUMMY LOGIC ---


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main single-page interface."""
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    """
    Handle file upload and return deepfake prediction.

    Expects a multipart/form-data POST with a 'file' field.
    Returns JSON: { label, confidence, file_type, error? }
    """

    # 1. Validate that a file was actually sent
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    # 2. Validate extension
    if not allowed_file(file.filename):
        return jsonify({
            "error": "Unsupported file type. Please upload JPG, PNG, or MP4."
        }), 415

    # 3. Save the file with a unique name to avoid conflicts
    original_name = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    file.save(file_path)

    file_type = get_file_type(original_name)

    # 4. Run prediction
    try:
        result = predict_deepfake(file_path, file_type)
    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500

    # 5. Clean up the uploaded file after prediction (no persistence needed)
    if os.path.exists(file_path):
        os.remove(file_path)

    # 6. Return result
    return jsonify({
        "label": result["label"],
        "confidence": result["confidence"],
        "details": result["details"],
        "file_type": file_type,
    })


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n  Deepfake Detector running → http://127.0.0.1:5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
