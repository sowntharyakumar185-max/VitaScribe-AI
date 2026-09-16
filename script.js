document.addEventListener('DOMContentLoaded', () => {
    const recordBtn = document.getElementById('recordBtn');
    const stopBtn = document.getElementById('stopBtn');
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    const statusDiv = document.getElementById('status');
    const loader = document.getElementById('loader');
    const resultsDiv = document.getElementById('results');
    const transcriptionText = document.getElementById('transcriptionText');
    const summaryText = document.getElementById('summaryText');

    let mediaRecorder;
    let audioChunks = [];

    // Toggle Logic
    const meetingModeToggle = document.getElementById('meetingModeToggle');
    const modeLabel = document.getElementById('modeLabel');

    meetingModeToggle.addEventListener('change', () => {
        if (meetingModeToggle.checked) {
            modeLabel.textContent = "Meeting Mode 🖥️";
            statusDiv.textContent = "Mode: Capturing System Audio (Share Screen)";
        } else {
            modeLabel.textContent = "Mic Mode 🎤";
            statusDiv.textContent = "Mode: Microphone Recording";
        }
    });

    // Recording Logic
    recordBtn.addEventListener('click', async () => {
        try {
            let stream;
            if (meetingModeToggle.checked) {
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
                // Mic Mode: Standard Microphone
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            }

            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                processAudio(audioBlob, "recorded_audio.wav");

                // Stop all tracks (Video & Audio)
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            recordBtn.classList.add('hidden');
            stopBtn.classList.remove('hidden');
            statusDiv.textContent = meetingModeToggle.checked ? "Records System Audio..." : "Recording Microphone...";
            resultsDiv.classList.add('hidden');

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

    // Upload Logic
    uploadBtn.addEventListener('click', () => {
        const file = fileInput.files[0];
        if (file) {
            processAudio(file, file.name);
        } else {
            statusDiv.textContent = "Please select a file first.";
        }
    });

    // Translation Logic
    const translateBtn = document.getElementById('translateBtn');
    const languageSelect = document.getElementById('languageSelect');

    translateBtn.addEventListener('click', async () => {
        const summary = summaryText.textContent;
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
                body: JSON.stringify({ summary: summary, language: targetLang })
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
                    summary: summaryText.textContent
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

        const formData = new FormData();
        formData.append('audio', blob, filename);

        try {
            const response = await fetch('/record', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();

            transcriptionText.textContent = data.text;
            summaryText.textContent = data.summary;

            resultsDiv.classList.remove('hidden');
            statusDiv.textContent = "Done!";
        } catch (error) {
            console.error("Error:", error);
            statusDiv.textContent = "An error occurred during processing.";
        } finally {
            loader.style.display = 'none';
        }
    }
});
