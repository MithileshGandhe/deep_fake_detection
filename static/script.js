/**
 * script.js — Deepfake Detector Frontend Logic
 * =============================================
 * Handles:
 *  - Drag & drop file selection
 *  - File preview (image / video)
 *  - Upload + fetch() call to /predict
 *  - Loading steps animation
 *  - Result rendering with confidence bar
 *  - Reset / "Analyse Another" flow
 */

// ── Element References ──────────────────────────────────────────────────────

const dropZone        = document.getElementById("drop-zone");
const fileInput       = document.getElementById("file-input");
const errorMsg        = document.getElementById("error-msg");
const previewWrapper  = document.getElementById("preview-wrapper");
const previewBox      = document.getElementById("preview-box");
const fileName        = document.getElementById("file-name");
const btnClear        = document.getElementById("btn-clear");
const btnAnalyse      = document.getElementById("btn-analyse");

const uploadSection   = document.getElementById("upload-section");
const loadingSection  = document.getElementById("loading-section");
const resultSection   = document.getElementById("result-section");

const step1El         = document.getElementById("step-1");
const step2El         = document.getElementById("step-2");
const step3El         = document.getElementById("step-3");

const resultIcon      = document.getElementById("result-icon");
const resultLabel     = document.getElementById("result-label");
const confidenceVal   = document.getElementById("confidence-val");
const confidenceBar   = document.getElementById("confidence-bar");
const resultDetails   = document.getElementById("result-details");
const btnAgain        = document.getElementById("btn-again");

// ── State ───────────────────────────────────────────────────────────────────

/** Currently selected File object (or null) */
let selectedFile = null;

/** Timer ID for the loading steps animation */
let stepsTimerId = null;

// ── Drag & Drop ─────────────────────────────────────────────────────────────

// Open file picker when the drop zone is clicked or keyboard-activated
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

// Highlight drop zone while dragging over it
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));

// Handle dropped file
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const files = e.dataTransfer.files;
  if (files.length > 0) handleFileSelection(files[0]);
});

// Handle file picker selection
fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) handleFileSelection(fileInput.files[0]);
});

// ── File Handling ────────────────────────────────────────────────────────────

/**
 * Validate and preview a selected file.
 * @param {File} file
 */
function handleFileSelection(file) {
  clearError();

  // Validate type
  const allowedTypes = ["image/jpeg", "image/png", "video/mp4"];
  if (!allowedTypes.includes(file.type)) {
    showError("Unsupported file type. Please upload a JPG, PNG, or MP4 file.");
    return;
  }

  // Validate size (100 MB)
  if (file.size > 100 * 1024 * 1024) {
    showError("File is too large. Maximum allowed size is 100 MB.");
    return;
  }

  selectedFile = file;
  renderPreview(file);
}

/**
 * Show image or video preview inside the preview box.
 * @param {File} file
 */
function renderPreview(file) {
  // Clear previous preview
  previewBox.innerHTML = "";

  const url = URL.createObjectURL(file);

  if (file.type.startsWith("image/")) {
    const img = document.createElement("img");
    img.src = url;
    img.alt = "Selected image preview";
    previewBox.appendChild(img);
  } else {
    const video = document.createElement("video");
    video.src = url;
    video.controls = true;
    video.muted = true;
    video.playsInline = true;
    previewBox.appendChild(video);
  }

  fileName.textContent = file.name;
  previewWrapper.hidden = false;
}

// Remove selected file
btnClear.addEventListener("click", () => {
  resetSelection();
});

// ── Analyse Button ───────────────────────────────────────────────────────────

btnAnalyse.addEventListener("click", () => {
  clearError();

  if (!selectedFile) {
    showError("Please select a file before analysing.");
    return;
  }

  startAnalysis();
});

// ── Analysis Flow ────────────────────────────────────────────────────────────

/**
 * Transition to loading state and send file to the backend.
 */
async function startAnalysis() {
  // Switch sections
  showSection("loading");
  animateLoadingSteps();

  // Build form data
  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const response = await fetch("/predict", {
      method: "POST",
      body: formData,
    });

    // Stop loading steps animation
    clearTimeout(stepsTimerId);

    if (!response.ok) {
      // Try to parse server error message
      let errText = `Server responded with status ${response.status}.`;
      try {
        const errJson = await response.json();
        if (errJson.error) errText = errJson.error;
      } catch (_) { /* ignore */ }
      showSection("upload");
      showError(errText);
      return;
    }

    const data = await response.json();
    renderResult(data);

  } catch (networkError) {
    clearTimeout(stepsTimerId);
    showSection("upload");
    showError("Network error: could not reach the server. Make sure the Flask app is running.");
    console.error("Fetch error:", networkError);
  }
}

/**
 * Animate the loading step pills sequentially.
 */
function animateLoadingSteps() {
  // Reset all steps
  [step1El, step2El, step3El].forEach(el => el.classList.remove("active"));
  step1El.classList.add("active");

  stepsTimerId = setTimeout(() => {
    step1El.classList.remove("active");
    step2El.classList.add("active");

    stepsTimerId = setTimeout(() => {
      step2El.classList.remove("active");
      step3El.classList.add("active");
    }, 900);
  }, 700);
}

// ── Result Rendering ──────────────────────────────────────────────────────────

/**
 * Populate and show the result section.
 * @param {{ label: string, confidence: number, details: string, file_type: string }} data
 */
function renderResult(data) {
  const isReal = data.label === "REAL";

  // Icon
  resultIcon.textContent = isReal ? "✅" : "⚠️";

  // Label
  resultLabel.textContent = isReal ? "REAL" : "FAKE";
  resultLabel.className = "result-label " + (isReal ? "real" : "fake");

  // Confidence
  const pct = Math.round(data.confidence * 100);
  confidenceVal.textContent = `${pct}%`;

  // Animate confidence bar after brief delay
  confidenceBar.style.width = "0";
  confidenceBar.className = "confidence-bar-fill " + (isReal ? "real" : "fake");
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      confidenceBar.style.width = `${pct}%`;
    });
  });

  // Details text
  resultDetails.textContent = data.details;

  // Show result section
  showSection("result");
}

// ── Reset ─────────────────────────────────────────────────────────────────────

/** "Analyse Another File" button */
btnAgain.addEventListener("click", () => {
  resetSelection();
  showSection("upload");
});

/**
 * Clear the selected file, preview, and error state.
 */
function resetSelection() {
  selectedFile = null;
  previewBox.innerHTML = "";
  previewWrapper.hidden = true;
  fileInput.value = "";
  clearError();
}

// ── Section Switcher ──────────────────────────────────────────────────────────

/**
 * Show one section and hide the others.
 * @param {"upload" | "loading" | "result"} name
 */
function showSection(name) {
  uploadSection.hidden  = name !== "upload";
  loadingSection.hidden = name !== "loading";
  resultSection.hidden  = name !== "result";
}

// ── Error Helpers ─────────────────────────────────────────────────────────────

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.hidden = false;
}

function clearError() {
  errorMsg.textContent = "";
  errorMsg.hidden = true;
}
