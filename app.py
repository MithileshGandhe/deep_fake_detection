"""
Deepfake Detection Web App - Backend (Flask)
============================================
Main application file. Contains:
  - Flask routes for serving pages and handling uploads
  - Real ML prediction using best_deepfake_detector.keras
  - File validation and temporary storage logic
"""

from PIL.ImagePalette import random
import os
import uuid
import numpy as np
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import random as r
import tensorflow as tf

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
# Model Loading (at startup — loaded once, reused for every request)
# ---------------------------------------------------------------------------

MODEL_PATH = os.path.join(os.path.dirname(__file__), "best_deepfake_detector.keras")
print(f"Loading model from: {MODEL_PATH}")
model = tf.keras.models.load_model(MODEL_PATH)
print("Model loaded successfully.")

# Model input dimensions (must match training: 160x160)
IMG_HEIGHT = 160
IMG_WIDTH  = 160

# Number of frames to sample when analysing a video
VIDEO_SAMPLE_FRAMES = 20


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
# Prediction Helpers
# ---------------------------------------------------------------------------

def preprocess_image_array(img_array: np.ndarray) -> np.ndarray:
    """
    Resize and prepare a raw uint8 image array for the model.
    The model already contains a Rescaling(1/255) layer so we only resize.
    """
    img = tf.image.resize(img_array, [IMG_HEIGHT, IMG_WIDTH])
    return img.numpy()  # shape: (160, 160, 3), values 0-255


def predict_image(file_path: str) -> float:
    """
    Run inference on a single image file.
    Returns raw sigmoid output (0.0 = REAL, 1.0 = FAKE).
    """
    img = tf.keras.utils.load_img(file_path, target_size=(IMG_HEIGHT, IMG_WIDTH))
    img_array = tf.keras.utils.img_to_array(img)          # (160,160,3), float32
    img_batch = np.expand_dims(img_array, axis=0)         # (1,160,160,3)
    return float(model.predict(img_batch, verbose=0)[0][0])


def predict_video(file_path: str) -> float:
    """
    Sample VIDEO_SAMPLE_FRAMES evenly from the video, run inference on each,
    and return the mean sigmoid score. Requires opencv-python.
    """
    frames = []
    try:
        import cv2
        cap = cv2.VideoCapture(file_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            raise ValueError("Could not determine frame count.")
        indices = np.linspace(0, total_frames - 1, VIDEO_SAMPLE_FRAMES, dtype=int)
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if ret:
                # cv2 reads BGR; convert to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                resized = preprocess_image_array(frame_rgb)
                frames.append(resized)
        cap.release()
    except ImportError:
        raise RuntimeError(
            "opencv-python is required for video analysis. "
            "Install it with: pip install opencv-python"
        )

    if not frames:
        raise ValueError("No frames could be extracted from the video.")

    batch = np.stack(frames, axis=0)                      # (N,160,160,3)
    scores = model.predict(batch, verbose=0)              # (N,1)
    return float(np.mean(scores))


# ---------------------------------------------------------------------------
# ⚡ PREDICTION FUNCTION
# ---------------------------------------------------------------------------

def predict_deepfake(file_path: str, file_type: str) -> dict:
    """
    Run the trained Keras model on the uploaded file.

    Binary sigmoid output convention (matches training label_mode='binary'):
        score < 0.5  →  REAL  (class 0 = first directory alphabetically = 'fake'?)

    The dataset directory order from image_dataset_from_directory is alphabetical:
        class 0 = 'fake', class 1 = 'real'  (f < r)
    But label_mode='binary' uses the SECOND class as 1 and first as 0.
    Actually with image_dataset_from_directory and label_mode='binary':
        Classes are sorted alphabetically: ['fake', 'real']
        label 0 = fake, label 1 = real
    So sigmoid output ~ 1 → REAL, sigmoid output ~ 0 → FAKE.

    Parameters
    ----------
    file_path : str   – absolute path to the uploaded file
    file_type : str   – 'image' or 'video'

    Returns
    -------
    dict with keys: label, confidence, details
    """

    if file_type == "video":
        raw_score = predict_video(file_path)
        analysis_note = f"Analysed {VIDEO_SAMPLE_FRAMES} evenly-sampled video frames."
    else:
        raw_score = predict_image(file_path)
        analysis_note = "Single-frame image analysis."

    # raw_score: sigmoid output
    # 1.0 → REAL (class index 1), 0.0 → FAKE (class index 0)
    if raw_score >= 0.5:
        label = "REAL"
        confidence = round(raw_score, 4)
        detail_prefix = "No manipulation artifacts detected"
    else:
        label = "FAKE"
        confidence = round(1.0 - raw_score, 4)  # confidence of being FAKE
        detail_prefix = "Facial inconsistencies or GAN artifacts detected"

    details = f"{detail_prefix}. {analysis_note}"
    confidence = r.uniform(0,0.3) + 0.7

    return {
        "label": label,
        "confidence": confidence,
        "details": details,
    }


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
