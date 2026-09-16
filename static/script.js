document.addEventListener('DOMContentLoaded', () => {
    const recordBtn = document.getElementById('recordBtn');
    const stopBtn = document.getElementById('stopBtn');
    const uploadBtn = document.getElementById('uploadBtn'); // may be null (upload removed)
    const fileInput = document.getElementById('fileInput'); // may be null (upload removed)
    const statusDiv = document.getElementById('status');
    const loader = document.getElementById('loader');
    const resultsDiv = document.getElementById('results');
    const transcriptionText = document.getElementById('transcriptionText');
    const summaryText = document.getElementById('summaryText');
    const editableText = document.getElementById('editableText');
    const generateBtn = document.getElementById('generateBtn');
    const wrongTermInput = document.getElementById('wrongTermInput');
    const correctTermInput = document.getElementById('correctTermInput');
    const addTermBtn = document.getElementById('addTermBtn');
    const dictionaryList = document.getElementById('dictionaryList');
    const dictionaryStatus = document.getElementById('dictionaryStatus');

    let currentVisitId = null;
    let lastTranscription = "";
    let baseSummaryForTranslation = "";

    let mediaRecorder;
    let audioChunks = [];
    let recordingStartTime = 0;

    function escapeHtml(value) {
        return (value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    async function loadMedicalDictionary() {
        if (!dictionaryList) return;
        try {
            const resp = await fetch('/medical-terms/list');
            const data = await resp.json();
            if (!resp.ok || data.error) {
                dictionaryStatus.textContent = data.error || 'Failed to load dictionary.';
                return;
            }
            const terms = data.terms || [];
            if (!terms.length) {
                dictionaryList.innerHTML = '<div class="status-text">No terms added yet.</div>';
                return;
            }
            dictionaryList.innerHTML = terms.map(term => `
                <div class="dict-row">
                    <span><b>${escapeHtml(term.wrong_term)}</b> -> ${escapeHtml(term.correct_term)}</span>
                    <button class="btn danger dict-delete-btn" data-id="${term.id}">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </div>
            `).join('');

            document.querySelectorAll('.dict-delete-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = btn.getAttribute('data-id');
                    try {
                        const delResp = await fetch('/medical-terms/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ term_id: id })
                        });
                        const delData = await delResp.json();
                        if (!delResp.ok || delData.error) {
                            dictionaryStatus.textContent = delData.error || 'Failed to delete term.';
                            dictionaryStatus.style.color = 'red';
                            return;
                        }
                        dictionaryStatus.textContent = 'Term deleted.';
                        dictionaryStatus.style.color = 'green';
                        loadMedicalDictionary();
                    } catch (e) {
                        dictionaryStatus.textContent = 'Delete failed: ' + e.message;
                        dictionaryStatus.style.color = 'red';
                    }
                });
            });
        } catch (e) {
            dictionaryStatus.textContent = 'Failed to load dictionary: ' + e.message;
            dictionaryStatus.style.color = 'red';
        }
    }

    if (addTermBtn && wrongTermInput && correctTermInput) {
        addTermBtn.addEventListener('click', async () => {
            const wrongTerm = wrongTermInput.value.trim();
            const correctTerm = correctTermInput.value.trim();
            if (!wrongTerm || !correctTerm) {
                dictionaryStatus.textContent = 'Please enter both misheard and correct terms.';
                dictionaryStatus.style.color = 'red';
                return;
            }
            try {
                const resp = await fetch('/medical-terms/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        wrong_term: wrongTerm,
                        correct_term: correctTerm
                    })
                });
                const data = await resp.json();
                if (!resp.ok || data.error) {
                    dictionaryStatus.textContent = data.error || 'Failed to save term.';
                    dictionaryStatus.style.color = 'red';
                    return;
                }
                dictionaryStatus.textContent = 'Medical term saved.';
                dictionaryStatus.style.color = 'green';
                wrongTermInput.value = '';
                correctTermInput.value = '';
                loadMedicalDictionary();
            } catch (e) {
                dictionaryStatus.textContent = 'Save failed: ' + e.message;
                dictionaryStatus.style.color = 'red';
            }
        });

        loadMedicalDictionary();
    }

    // Toggle Logic (optional meeting mode)
    const meetingModeToggle = document.getElementById('meetingModeToggle');
    const modeLabel = document.getElementById('modeLabel');

    if (meetingModeToggle && modeLabel) {
        meetingModeToggle.addEventListener('change', () => {
            if (meetingModeToggle.checked) {
                modeLabel.textContent = "Meeting Mode 🖥️";
                statusDiv.textContent = "Mode: Capturing System Audio (Share Screen)";
            } else {
                modeLabel.textContent = "Mic Mode 🎤";
                statusDiv.textContent = "Mode: Microphone Recording";
            }
        });
    }

    // Recording Logic
    recordBtn.addEventListener('click', async () => {
        // Basic support checks so we fail gracefully instead of crashing
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            statusDiv.textContent = "Error: This browser does not support audio recording.";
            return;
        }
        if (typeof MediaRecorder === "undefined") {
            statusDiv.textContent = "Error: MediaRecorder is not available in this browser.";
            return;
        }
        try {
            let stream;
            if (meetingModeToggle && meetingModeToggle.checked) {
                // Meeting Mode: Capture System Audio (via Screen Share)
                // Note: User must select "Share System Audio" in the browser prompt
                stream = await navigator.mediaDevices.getDisplayMedia({
                    video: true,
                    audio: true
                });

                // Check if user actually shared audio
                if (stream.getAudioTracks().length === 0) {
                    stream.getTracks().forEach(track => track.stop()); // Stop video
                    alert("⚠️ No System Audio found! \n\nPlease check the 'Share System Audio' box in the screen share popup.");
                    return;
                }
            } else {
                // Mic Mode: Standard Microphone with speech-friendly constraints
                stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        sampleRate: 48000,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });
            }

            // Prefer a widely supported audio container (webm/opus) for reliable backend conversion
            const preferredMimeTypes = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/ogg;codecs=opus',
                'audio/ogg'
            ];
            let chosenMimeType = '';
            for (const t of preferredMimeTypes) {
                if (MediaRecorder.isTypeSupported(t)) {
                    chosenMimeType = t;
                    break;
                }
            }

            mediaRecorder = chosenMimeType ? new MediaRecorder(stream, { mimeType: chosenMimeType }) : new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const durationMs = Date.now() - recordingStartTime;
                if (durationMs < 1500) {
                    statusDiv.textContent = "Recording too short. Please speak for at least 2-3 seconds.";
                    stream.getTracks().forEach(track => track.stop());
                    return;
                }

                const blobType = mediaRecorder.mimeType || (audioChunks[0] && audioChunks[0].type) || 'audio/webm';
                const audioBlob = new Blob(audioChunks, { type: blobType });
                const ext = blobType.includes('ogg') ? 'ogg' : 'webm';
                processAudio(audioBlob, `recorded_audio.${ext}`);

                // Stop all tracks (Video & Audio)
                stream.getTracks().forEach(track => track.stop());
            };

            recordingStartTime = Date.now();
            mediaRecorder.start(250);
            recordBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            statusDiv.textContent = (meetingModeToggle && meetingModeToggle.checked)
                ? "Recording system audio..."
                : "Recording microphone...";
            resultsDiv.classList.add('hidden');
            if (generateBtn) generateBtn.disabled = true;

        } catch (err) {
            console.error("Error accessing media:", err);
            statusDiv.textContent = "Error: Could not start recording. " + err.message;
        }
    });

    stopBtn.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            recordBtn.classList.remove('hidden');
            stopBtn.classList.add('hidden');
            statusDiv.textContent = "Processing audio...";
        }
    });

    // Upload Logic (optional; UI removed for real-time diagnosis)
    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => {
            const file = fileInput.files[0];
            if (file) {
                processAudio(file, file.name);
            } else {
                statusDiv.textContent = "Please select a file first.";
            }
        });
    }

    // Translation Logic
    const translateBtn = document.getElementById('translateBtn');
    const languageSelect = document.getElementById('languageSelect');

    translateBtn.addEventListener('click', async () => {
        const summary = (baseSummaryForTranslation || summaryText.textContent || "").trim();
        const targetLang = languageSelect.value;
        const originalBtnText = translateBtn.innerHTML;

        if (!summary || summary === "...") {
            alert("No summary to translate. Please record audio first.");
            return;
        }

        translateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Translating...';
        translateBtn.disabled = true;

        try {
            const response = await fetch('/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    summary: summary,
                    language: targetLang,
                    source_language: 'en',
                    visit_id: currentVisitId
                })
            });

            const data = await response.json();

            if (data.error) {
                alert("Translation Error: " + data.error);
            } else {
                summaryText.textContent = data.translated_summary;
            }
        } catch (error) {
            console.error("Translation Error:", error);
            alert("Failed to translate.");
        } finally {
            translateBtn.innerHTML = originalBtnText;
            translateBtn.disabled = false;
        }
    });

    // Email Logic
    const sendEmailBtn = document.getElementById('sendEmailBtn');
    const emailInput = document.getElementById('emailInput');
    const emailStatus = document.getElementById('emailStatus');

    sendEmailBtn.addEventListener('click', async () => {
        const email = emailInput.value;
        if (!email) {
            emailStatus.textContent = "Please enter an email address.";
            emailStatus.style.color = "red";
            return;
        }

        emailStatus.textContent = "Sending...";
        emailStatus.style.color = "#636e72";

        try {
            const response = await fetch('/send-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    summary: summaryText.textContent,
                    visit_id: currentVisitId
                })
            });

            if (response.ok) {
                emailStatus.textContent = "Email sent successfully!";
                emailStatus.style.color = "green";
            } else {
                let errorMsg = "Failed to send email.";
                try {
                    const text = await response.text();
                    try {
                        const errorData = JSON.parse(text);
                        errorMsg = errorData.error || errorMsg;
                    } catch (e) {
                        console.error("Non-JSON error response:", text);
                        errorMsg = `Server Error (${response.status}): ` + (text.substring(0, 50) + "...") || "Unknown error";
                    }
                } catch (readError) {
                    console.error("Error reading response:", readError);
                }
                emailStatus.textContent = errorMsg;
                emailStatus.style.color = "red";
            }
        } catch (error) {
            console.error("Error sending email:", error);
            emailStatus.textContent = "Error sending email: " + error.message;
            emailStatus.style.color = "red";
        }
    });

    async function processAudio(blob, filename) {
        statusDiv.textContent = "Uploading and processing...";
        loader.style.display = 'block';
        resultsDiv.classList.add('hidden');
        if (generateBtn) generateBtn.disabled = true;

        const formData = new FormData();
        formData.append('audio', blob, filename);
        const speechLanguage = document.getElementById('speechLanguage');
        formData.append('language', speechLanguage ? (speechLanguage.value || 'auto') : 'auto');

        // Attach patient details so the backend can include them in the PDF
        const patientNameInput = document.getElementById('patientName');
        const ageInput = document.getElementById('age');
        const weightInput = document.getElementById('weight');
        const genderSelect = document.getElementById('gender');
        const doctorNameInput = document.getElementById('doctorName');

        if (patientNameInput) {
            formData.append('patient_name', patientNameInput.value || '');
        }
        if (ageInput) {
            formData.append('age', ageInput.value || '');
        }
        if (weightInput) {
            formData.append('weight', weightInput.value || '');
        }
        if (genderSelect) {
            formData.append('gender', genderSelect.value || '');
        }
        if (doctorNameInput) {
            formData.append('doctor_name', doctorNameInput.value || '');
        }

        try {
            const response = await fetch('/record', {
                method: 'POST',
                body: formData
            });

            const rawText = await response.text();

            if (!response.ok) {
                // Try to surface the backend error message so it's easier to debug
                try {
                    const errData = JSON.parse(rawText);
                    statusDiv.textContent = errData.error || `Server error: ${response.status}`;
                } catch (e) {
                    statusDiv.textContent = `Server error ${response.status}: ${rawText.substring(0, 120)}`;
                }
                return;
            }

            const data = JSON.parse(rawText);

            lastTranscription = data.text || "";
            transcriptionText.textContent = lastTranscription || "...";
            summaryText.textContent = "Edit the text above, then click 'Generate Structured PDF'.";
            currentVisitId = null;
            baseSummaryForTranslation = "";
            if (editableText) editableText.value = lastTranscription || "";
            if (generateBtn) generateBtn.disabled = !(editableText && editableText.value.trim().length > 0);

            resultsDiv.classList.remove('hidden');
            statusDiv.textContent = "Transcription ready. You can edit and generate the report.";
        } catch (error) {
            console.error("Error during /record:", error);
            statusDiv.textContent = "An error occurred during processing: " + error.message;
        } finally {
            loader.style.display = 'none';
        }
    }

    // Enable/disable generate button based on edited text
    if (editableText && generateBtn) {
        editableText.addEventListener('input', () => {
            generateBtn.disabled = editableText.value.trim().length === 0;
        });
    }

    // Generate structured report & PDF from edited text
    if (generateBtn) {
        generateBtn.addEventListener('click', async () => {
            const textToUse = (editableText ? editableText.value : lastTranscription).trim();
            if (!textToUse) {
                alert("No text available. Please record first.");
                return;
            }

            // Patient details
            const patientNameInput = document.getElementById('patientName');
            const ageInput = document.getElementById('age');
            const weightInput = document.getElementById('weight');
            const genderSelect = document.getElementById('gender');
            const doctorNameInput = document.getElementById('doctorName');

            const payload = {
                text: textToUse,
                patient_name: patientNameInput ? patientNameInput.value || "" : "",
                age: ageInput ? ageInput.value || "" : "",
                weight: weightInput ? weightInput.value || "" : "",
                gender: genderSelect ? genderSelect.value || "" : "",
                doctor_name: doctorNameInput ? doctorNameInput.value || "" : ""
            };

            generateBtn.disabled = true;
            const original = generateBtn.innerHTML;
            generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
            statusDiv.textContent = "Generating structured prescription and PDF...";
            loader.style.display = 'block';

            try {
                const resp = await fetch('/generate-report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await resp.json();
                if (!resp.ok || data.error) {
                    throw new Error(data.error || `Server error: ${resp.status}`);
                }

                summaryText.textContent = data.summary || "";
                baseSummaryForTranslation = data.summary || "";
                currentVisitId = data.visit_id || null;
                statusDiv.textContent = "Report generated. You can download the PDF now.";
            } catch (e) {
                console.error(e);
                statusDiv.textContent = "Error generating report: " + e.message;
                generateBtn.disabled = false;
            } finally {
                generateBtn.innerHTML = original;
                loader.style.display = 'none';
            }
        });
    }
});
